# Archived HANDOFF_NEXT — session-by-session project history

> **Archived 2026-08-12:** this is the complete former 3,200-line working handoff. It is
> retained for measurements and failure history, but it no longer defines current work.
> Start at [HANDOFF_NEXT.md](../../HANDOFF_NEXT.md) in the repository root.

**Written 2026-08-03, current through 2026-08-12. This is the entry point for a cold session.**

> **For the completed Rankings ownership design, read
> `docs/archive/HANDOFF_RANKVWF.md`.** Its
> implementation, automated matrix and exact repeated manual Mesen route all pass.
> Treat the implementation and its regressions as one milestone when changing it later.

> ## CURRENT — RANKINGS/OROCHI R3 COMPLETE, 2026-08-12
>
> The current `main` working milestone passes the full local `sh build.sh`,
> including every supplied SRAM/state-backed route. The resulting ROM is
> `build/shiren_en.gb`, SHA-256
> `b5b45c3c95a3ff1305d36c0fbf1b538097f5fae7f3a5cf01146ac67ddb3a260f`.
> The matching shuffled and redirect-all matrix ROMs are SHA-256
> `c9842fec9c9ff02e2a9eb24eab5ecf64f5c2dda7cfc55c3776a93de48c628be1` and
> `7b8153b7d19a7e578f77fd872cbd7dd2039708599c79b9d592fb2b9ffa80591f`.
> This milestone is not a release freeze: Joey's full-game playtest is still the primary
> discovery pass. The former Rankings/Orochi blocker is closed: Joey completed the exact
> repeated Kuyo/Village Exit route in Mesen and reported it works. The frozen
> pre-repair diagnostic ROM remains available at SHA-256
> `b10ce9ccf1362072aeab1ec840714e7fd1964ba818f53456ba0a884c0426f40c`.
>
> Thin Pixel-7 GB Compact is now the production font for dialogue, menus and cinematics.
> Its reviewed production revision has properly lowered
> `g/p/q/y` descenders, tabular 5px numerals, the supplied punctuation refinements and
> centered compact `+`/`-`. The full translated corpus passes the physical/source audit;
> `tools/nameaudition.py` reports zero unsafe player-name lines for both `Shiren` and the
> widest legal six-character name. The prior Moonlit Sans and Dot Gothic assets remain
> only as comparison/history.
>
> The start screen now uses the viewer-supplied 160x144 four-colour design exactly:
> `Mystery Dungeon / Shiren / The Wanderer / Monster of Moonlight Village / GB`. Its
> 217 unique tiles occupy bank 62 `$7000-$7F43`, leaving 188 bytes. The embedded pack
> matches all 23,040 source pixels by shade; `tools/titlelogospill.py` verifies every tile,
> every map cell, the native fade and the unchanged PUSH START -> file-menu transition.
>
> V5C's town/dungeon cards now use Joey's separately approved clean Poppins Medium
> mock-ups. `Moonlight Village` and `1 Forest` are exact live-emulator raster matches; the
> three-row installer retains descenders and covers all eight labels plus every live floor
> field from 1 through 50. The baked source is
> `assets/graphics/arrival_cards_poppins.json`; ordinary builds do not depend on a TTF.
> Every native numbered form now gives its number and name one shared line origin and is
> centered from visible ink. `floormarkerspill.py` requires all 22 active numbered cards
> to have at most four pixels of outer-margin imbalance while replaying 72 exact emulator
> cases and every live value 1-50. The real Dragon's Maw Log-1 fixture selects floor 19
> and must occupy x=7..152 (exact 7/7px margins) in `dragonmawmarkerspill.py`.
>
> The same milestone closes the plated/cursed/unidentified equipment-marker VWF paths,
> including the Japanese-authentic pair of `$88` stars before a hidden equipment modifier
> is revealed. The separate identity-hidden Info branch is also closed: `13:$7E0D`
> bypasses the normal item-help table whenever `$CF7B` bit 7 is clear and returns the one
> directly embedded sentence at `13:$5537`. Its Japanese means “It is unidentified, so
> its effect is unclear”; `itemfix.py` replaces its exact 18 bytes with `Effect is
> unknown.` for every appearance/category. The same Info formatter copies the direct
> `みしきべつのアイテム` title at `4:$5773`; its 11-byte slot becomes the compact heading
> `Unknown`. `unidentifiedhelp.py` executes the real staging routine with extreme
> topic/unit selectors, while `identityhiddenspill.py` follows real Opal Bracer and Gold
> Staff five-choice action menus from the Dragon's Maw SRAM fixture and proves both title
> and body plane-exact.
>
> Empty Pot See is closed too. Screen 13's code-selected `4:$7464` literal means
> “Nothing is inside” and never enters the extracted item-help table. `itemfix.py`
> replaces only its asserted 14-byte slot with centered `Empty`; `potseespill.py` follows
> the supplied Storage Pot Floor -> See route and requires both exact `$C616` staging and
> visible proportional planes. Back/Todo Press behavior is closed separately with Joey's
> Log-2 fixture: their shared `$CC` expansion literal moved in place from `4:$7473` to
> `$7471` and now reads `Press`. `actionpotspill.py` selects genuine ID `$81` and `$88`
> independently and checks all three staged/VWF rows for each pot without menu spill.
>
> This milestone also renames the
> former Accurate Sword to `True Rapier`, repairs Gitan Floor -> Info dismissal for the
> real Log-3 three-choice route, and translates the active-dungeon Continue bubble to
> centered `Please` / `wait...`. `equipmentmarkerspill.py`, `unidentifiedspill.py`,
> `unidentifiedhelp.py`, `identityhiddenspill.py`,
> `menuglyphspill.py`, `gitaninfospill.py` and `waitcardspill.py` are permanent regressions.
> The dialogue selftest exercises all admitted glyphs at every shift, while the menu audit
> sends all 78 textual codes through Items and item Info plane-exact. The Gitan bug was the action-row finalizer
> waiting for four choices when Gitan has three; it left the LCD disabled after Info.
>
> The supplied Log-1 Decoy Staff route also closes a runtime-only name bug. Bank 11's
> actor-name producer at `$51D2` wrote Japanese bytes `$20,$18` (`にせ`) before copying
> the live player name. Thin Pixel-7 maps those bytes to `V`,`N`, so every action called
> the target `VNShiren`. Joey chose the compact label contract: use the live player name
> alone. `tools/decoyname.py` changes the existing branch at `11:$51D0` from conditional
> to unconditional, skipping only those two writes; custom player names and the native
> copy path remain intact. `--no-decoyname` is the one-byte control.
> `tools/decoynamespill.py` boots
> `saves/shiren_en_log_1_decoy_staff_enemy.srm`, loads Log 1, attacks the adjacent decoy
> and proves both actor payloads equal the live `$CF81` name with no prefix.
>
> The ordinary-stair bug was a false cross-bank reference, not companion selection.
> Bank-13 instructions at `$549F` and `$54B5` load `hl,$46C1`, explicitly select bank
> `$0E`, and call the dialogue stager. Their target is bank 14's `Go down / Stay here`,
> but extraction used to attach both operands to unrelated `13:$46C1`; repacking that
> message changed both loads to `$5AFD`, which is why companion dialogue appeared.
>
> State handoffs from the supplied SRAMs into the original Japanese code proved that two
> Koppa floors, Nagi and Fumi all stage only `14:$46C1`, then transition immediately after
> the default choice. There is no native companion line on this action. `extract.py` now
> records both proven overrides in `CROSS_BANK_IMMEDIATES`; the misleading runtime
> selector patch was removed. The historically named `tools/koppastairspill.py` checks
> the two rewritten operands, replays all four fixtures, requires the relocated English
> choice and rejects `$5AFD/$5B81/$7BC2` leakage.
>
> The supplied `shiren_en_log_1_talk_to_koppa.srm` exposed a second, independent control
> bug in `14:$7BC2`. Its Japanese source ends naturally at `$FF`, but the English appended
> `<end><brk>`, producing `message -> empty box -> closed`. The English now keeps its two
> lines and native terminator. `tools/koppatalkspill.py` requires one A to close the real
> town conversation, then points a diagnostic copy of the Koppa dungeon caller at the
> same record and requires one A to reach the next-floor card. Production ordinary stairs
> remain untouched and are still guarded by `koppastairspill.py`. `lint_en` now rejects a
> terminal `<end><brk>` added to bank-11/14 Japanese dialogue containing no `<end>`; the
> same unsafe suffix was removed from conservative Nagi interior `14:$5B81`.
>
> The final-exit freeze is **closed** using
> `saves/shiren_en_log_1_freeze_on_exit.srm`. It reproduced with Nagi too, proving the
> shared Rankings transition—not companion dialogue—was responsible. Rescue results
> arrive with the LCD disabled, but `rankvwf` armed the VBlank name-tile queue and waited
> for a consumer that cannot run while the LCD is off. The rank entry now selects a
> synchronous five-tile copy for each of its five rows in that state; the ordinary
> LCD-on title-menu Rankings route retains its queued upload. `tools/rescueexitspill.py`
> replays Down -> Go on and requires one complete Rankings page, five direct rows, zero
> queue arms, an enabled LCD and a nonblank settled result.
>
> **The supplied cleared-Orochi ownership repair is implemented and automated-green.**
> The one-bank settled board is one proportional `$80-$A6` allocation: 14 deduplicated
> heading/difficulty tiles plus five five-tile names. Kuyo/Village selectors use `$C0-$CB`
> only temporarily; the proven native loader restores `$00-$D2` before Rankings, title or
> Adventure maps reveal those planes. Live native board graphics remain disjoint. The
> ordinary LCD-on path retains queued 4+4+1 uploads, while the rescued-child LCD-off path
> retains five synchronous direct rows.
>
> The replacement `tools/orochisymbolspill.py` requires a `--no-menuvwf` native control
> and checks the actual `$CB/$CD/$CC/$CE` badge at rows 9-10 columns 5-6, complete
> Kuyo/Village boards, native status/OAM and repeated returns. It fails the frozen
> `b10ce9c...` known-bad ROM and passes the RC on normal, shuffled and redirect-all layouts,
> along with `rankspill`, `mainmenuspill`, `rescueexitspill`, `startspill`, `structspill`,
> `savesummaryspill`, the menu variants and `menuromspill`.
> `rankspill` retains its `--no-rankvwf` control for approved-name component comparisons,
> but uses the complete `--no-menuvwf` native control for legacy page 0 and nonzero page 1.
> Both pages delegate 5/5 rows and match the complete visible native board; page 1 proves
> prevalidation begins at `C6AC * 12` and catches the legacy code in its fifth selected row.
> `build.sh` now builds both controls and runs this regression when the supplied ranking
> SRAM is present.
>
> **Manual Mesen verdict PASSED 2026-08-12.** Joey used the final RC and authoritative
> Orochi SRAM for `Adventure -> Log 1 -> Rank/Pass -> Rank -> Kuyo -> Adventure -> Log 1`,
> repeated the Kuyo/Adventure cycle, then inspected `Village Exit` and returned to
> Adventure Log 1. VWF and the native graphics remained correct.
>
> `tools/rescuespill.py` remains the independent Nagi fixture. Its
> `saves/shiren_en_rescue.srm` fixture is Log 1 with **Nagi** following and deliberately
> validates the conservative records `14:$5AFD`, `14:$5B81` and `14:$70BE`, while proving
> the ordinary stair does not enter them and instead stages `Go down / Stay here`.
>
> Erasing Log 3 from the copied Koppa-v2 fixture exposed a title-menu allocator lifetime:
> the rebuilt eight-row menu inserted `New Log` and `Copy Log`, but `Copy Log` inherited
> the four-tile record formerly owned by `Rename` and fell back to fixed-width drawing.
> The first direct-Erase regression did not cover Joey's complete route: Load Log 1 ->
> Quit -> return to title -> Erase Log 3. Quit leaves gameplay value `$3A` in `$C0D7`,
> which the title hook had mistaken for an active VWF transaction and therefore skipped
> all setup. `menuvwf` now recognizes the exact complete title row-0 shape (`x=0,y=1`)
> before inspecting that byte, clears it, and begins a fresh dynamic allocation epoch.
> Selectors and overlays retain the parent title records behind them.
> The local fixtures are `saves/shiren_en_log_3_erase_copy_log_vwf.srm` and
> `saves/shiren_en_log_1_quit_erase_copy_log_vwf.srm`; both are byte-identical copies of
> the supplied Koppa-v2 SRAM. `tools/copylogspill.py` runs both routes, requiring all
> eight rebuilt rows—especially `Copy Log`—to be shadow- and plane-exact in each LCD state.
>
> Three later Log-1 fixtures close the save-summary location row itself. Bank 4's native
> producer always advanced four cells before copying a place, so a numberless
> `Dragon's Maw` retained a fixed-width indent. Numbered long names exceeded the legacy
> 14-cell row: `19F Dragon's Maw` stored `aw` where row 2 begins, consumed its terminator,
> and prevented `Hard` from drawing. `menuvwf` now removes the indent only when no floor
> prefix exists, copies a genuinely overflowing row to private staging, clears only its
> original spill, and restores the native next-row pointer after VWF composition. The
> summary pool is 9+10+8 tiles (`$DE-$F8`). `tools/savesummaryspill.py` boots
> `shiren_en_log_1_talk_to_koppa.srm`, `shiren_en_log_1_dragons_maw.srm`, and
> `shiren_en_log_1_fixed_width_save_info.srm`; all three exact payloads, `Hard`, shadow
> cells and both planes are permanent build gates when those local saves are present.
>
> **V5D ending credits is complete:** the supplied Hard-ending save proves all 22 native
> cards remain present, in order, with their native durations, translated in the approved
> white/green Poppins style. The separate Japanese end mark remains native by request.
> The first installer mistakenly uploaded the asset's row-major 20x2 strips to a native
> tilemap that addresses top/bottom tiles in interleaved pairs, producing scrambled text.
> The regression had compared VRAM to the same bad payload. The installer now interleaves
> each strip, and `endingcreditspill.py` reconstructs the tilemap plus compares every
> fully faded on-screen card against the approved raster.
> Continue ordinary wording/pacing and newly reached route findings through V4B. Then
> freeze the assets/text for V6 and run the clean-build,
> normal/shuffled/redirect-all, intro/ending and broad route/crash batteries.

> ## CURRENT — V4E MAIN-MENU TRANSITIONS COMPLETE, 2026-08-10
>
> Commit `393a543` fixes the title/file-menu stale-text routes and closes the previously
> scheduled V4E work. Difficulty text no
> longer shares `$67-$7A` with live title and Log-selector rows; it uses isolated
> `$E0-$F3`. Title, selector, summary, confirmation, difficulty and Rank/Pass composites
> are held LCD-off until one complete 20x18 shadow map is ready. Rankings is the exception:
> its native fields require the live VBlank queue, so it draws `$9800` behind a blank
> alternate `$9C00` map and flips back only from the authoritative page return.
>
> Fay's task screen now restores every borrowed heading/star/checkbox/separator plane while
> hidden and publishes only after its final prompt. The title entry is the official
> `Fay's Puzzles`; the proportional source contract was corrected so all 13 characters fit
> in eight tiles. `tools/mainmenuspill.py` permanently covers the supplied Log-3 difficulty
> and four-record Rankings routes. It, `startspill`, `rankspill`, and the full saved-route
> `structspill` suite pass normal, shuffled and redirect-all layouts with zero problems.
> Current ROM SHA-256:
> `0df21e78f009363787c327851035a19ff9f643b0b8ce305574cf736a52edf2d5`.

> ## CURRENT — V4F COMPLETE; PATH STATUS POLISH, 2026-08-10
>
> Branch `vwf-item-menu` uses `saves/shiren_en_item_menu.srm` as the authoritative route:
> it boots the single log, opens Menu -> Items, visits four unique inventory pages with
> Right/Left, and includes the short final page. The old ROM fails all six captured
> transitions (initial entry plus five page changes) with progressively mixed rows.
>
> The exact item row-0 boundary now waits for VBlank and disables the LCD before reused
> VWF slices change. The five item rows and following box-14 `Items` header compose while
> the screen is white; header completion publishes the full 20x18 shadow map and restores
> the LCD. A short page pre-stages its empty row 4 before the same publish boundary. The
> native cursor/page-arrow writers then finish normally; `$C382` is verified as the row-0
> cursor after every transition. The separate starting-menu V4E scope is now closed by the
> completion block above.
>
> Joey approved the white-flash transition in emulator on 2026-08-10: “it is perfect.”
> The approval screenshot then exposed an older box-14 defect: `Items` was a raw 8px `I`
> followed by proportional `tems`. Box 14 inherited a first-cell preservation bit solely
> from synthetic forced screen 1, where an invalid-context cursor overwrites that cell;
> ordinary item-menu play never does. Box 14 now composes the complete word, while the
> genuinely live `Which?`/`Pot` first-cell exceptions remain unchanged. Joey then
> spot-checked that correction and approved the complete proportional heading.
>
> The exact `saves/shiren_en_item_menu_wood_arrow.srm` route exposed the same underlying
> redraw order in Floor -> Info: action -> page 1, page 1 -> page 2, and page 2 -> action
> each showed mixed old/new VWF text. `tools/floorinfospill.py` now owns those three
> transitions. Help row 0 starts an LCD-off transaction before reused pixels change; the
> final help row pre-stages its empty row, border, arrow and page counter before publishing
> one complete 20x18 map. Returning through screen 0 stays hidden until screen 20's final
> action row and bottom edge are complete. The native cursor follows normally.
>
> `tools/itempagespill.py` and `tools/floorinfospill.py` are the permanent rendered-frame
> tests. Joey spot-checked the exact Wood Arrow action -> Info -> page 2 -> action route
> on 2026-08-10 and approved it as perfect, closing the remaining V4F visual gate. Normal,
> shuffled and redirect-all builds each pass six atomic `old -> white -> complete`
> transitions and
> four unique inventory pages. All three Wood Arrow transitions pass on the same three
> layouts; the normal route measures 5/5/8 LCD-off frames. The
> legacy floor-7 SRAM test now records LCD-off frames as `WWWWW`
> and still proves plane-exact settled rows. Full build, long/help/seal/condition/ROM/start,
> timing/upload, Floor/rescue/new-game, 20,320 spill frames, and 48 normal/shuffled
> dungeon/town crash runs are green.
>
> The follow-up Path status polish uses `saves/shiren_en_path_select.srm`, whose active
> adventure is **Log 2**. The fixed-cell value is now `Easy` / `Normal` / `Hard` rather
> than `Easy` / `Nrm` / `Hard`; bank 4's padding table is 6/4/6 so every value ends at
> column 18. `tools/pathspill.py` selects all three modes through the real sign, reopens
> the status menu and proves the exact shadow/BG-map cells plus the preserved column-19
> border on normal, shuffled and redirect-all layouts. Current ROM SHA-256:
> `92db1e18d9318a2a9ac569b2c11b69ce769fefa56f630354e24fe3d85478f1c1`.

> ## CURRENT — V4C MENU GEOMETRY COMPLETE; VISUALLY APPROVED, 2026-08-10
>
> `Ground` is now `Floor` in both editable menu TSVs. Boxes 0/1, 6/39, 8, 18, 29,
> 33 and 47 are back at their Japanese geometry; cursor homes moved with boxes 0, 6/39
> and 29. Boxes 14 (`Items`) and 34 (`Weapon`) each shrank by one cell but remain one
> wider than Japanese, and box 17 (`Pot`) remains one wider, because their measured Dot
> ink does not fit the smaller interior. Boxes 20/21 (`Close/Exit/Quit`) also remain one
> wider: their descriptors have no callable draw site in the ROM, so there is no live
> context in which to prove a narrow proportional source scanner. Box 38 retains its
> original width at x=3 because x=5 aliases a lifetime-sensitive static-pool identity;
> box 41 was already two cells narrower than Japanese and stays that way.
>
> Narrow ROM rows now have an explicit descriptor bit and terminated 18-glyph source
> contract; ordinary rows keep the native width boundary. `menuromspill` has real branch
> coverage for conditional box 18 and box 24. Normal and shuffled builds pass saved-menu
> page flips/action verbs, all ROM rows, title/save/erase/Rank-Pass, rankings, structured
> status/Fay/name rows, help/seals, clear conditions, the real Floor route and new-game
> smoke with zero problems. `boxspill` saw zero spills in 20,320 text-visible frames.
> Joey completed the in-emulator visual/cursor review and approved the result on
> 2026-08-10. V4C is complete. Do not enlarge a box from appearance alone without
> preserving the measured source, pixel and lifetime checks.

> ## HISTORICAL — FLOOR HEADER + CONSERVATIVE NAGI INTERIORS, CORRECTED 2026-08-11
>
> Joey's two playtest reports were both real and neither was represented by the previous
> completeness claim. The Floor command screen is dispatcher screen 20, box 5
> (`x0,y0,w18`, `$C616`), with **one raw prefix cell**. The first attempted closure was
> wrong: `menuspill` injected a second zero that the game never stages, so it proved a
> synthetic two-cell path while Joey's real screen still fell back to fixed-width text.
> `saves/shiren_en_ground.srm` (Log 1, standing on an Iron Shield) established the real
> bytes as `00 Iron Shield FF`. `tools/groundspill.py` now boots that log normally, opens
> Menu → Floor, and checks dispatcher 20, the exact descriptor/source/bytes, a one-cell
> allocator record, visible proportional planes and frame residency. `build.sh` runs this
> authoritative route whenever the local save exists. Every `menuspill` mode also injects
> `True Rapier+99` with the corrected one-cell contract as a component regression.
> `menuromspill` also expects box 5's custom bit-5 marker separately from the one-cell
> ROM-prefix boxes 8/14/17.
>
> During the original Nagi-stair investigation the game was observed starting dialogue at
> `14:$5AFD`, eight bytes inside `14:$5AF5`, later staging `14:$5B81` inside `14:$5B5B`
> and `14:$70BE` inside `14:$70B7`. We now know those observations followed the corrupt
> ordinary-stair load. The original Japanese route does not enter them there. All three
> remain conservative editable records in `script/en.tsv` /
> `script/prose_draft.tsv`; the manifest is **1,422 records / 37,593 covered bytes**. Their
> parents stay address-pinned and all views use separate pool redirects, so translating
> one cannot overwrite another if another event really does enter one.
>
> The correct first stairs window is the shared `14:$46C1` choice, translated as
> `Go down / Stay here`. Pressing A chooses Descend and advances immediately. The former
> `Please lets hurry back! / I gotta pee` result was evidence of the cross-bank reference
> bug documented at the top of this handoff, not a route-specific contract.
>
> `tools/rescuespill.py` boots Log 1 from `saves/shiren_en_rescue.srm`, walks onto the stair,
> verifies all three conservative records, rejects their use on the ordinary action and
> photographs the shared choice. `build.sh` runs it automatically when that local save
> exists. `gbrun.py --dte-scan` now rejects any
> stager address that is neither a manifested start, a structurally proven line resume nor
> a control-only record; it validates resumes against the **built English layout**, not
> Japanese byte offsets. Twelve newly observed DTE candidates are `# BLOCK`ed in
> `script/dte_ok.tsv`: compressing them changed global repacking and made this real route
> blank/corrupt, so future `--append` runs skip them until that battery failure is
> deliberately solved.
>
> Current ROM: `build/shiren_en.gb`, SHA-256
> `3dcfa9003f0c377d8020aa116bbe4d9fffc28fb6623815988b49655668df00e7`.
> `build.sh`, all four menu modes, clear conditions, ROM rows, start flow, rankings,
> structured rows, new-game smoke, cinematic VM, dialogue model, logic diff, 20,320
> composer frames, and the real Floor and rescue routes are green. The immediately
> current font snapshot also passed **48 normal/shuffled dungeon/town crash runs
> (12 seeds each) with zero halts**; repeat that broad sweep on the frozen V6 candidate.
> Review images: `build/ground_live_fixed.png` and
> `build/rescue_stair_control_order.png`.
>
> **Completeness language is corrected:** `coverage.py` proves framed-byte coverage for
> known alphabets and checks declared runtime starts; it cannot prove that no unknown
> event pointer begins inside covered bytes. Route scans remain the discovery layer. It
> also checks all ten script-bank embedded/unframed hits against exact reviewed non-text
> declarations. Do not describe the ordinary script as unconditionally runtime-complete:
> the static candidates are resolved, but route coverage can always reveal a new interior
> entry such as the Nagi stair event.

> ## CURRENT — PROPORTIONAL VWF BUDGET RESET, 2026-08-09
>
> The old 18-cell native model, 24-character uniform-VWF model, and universal 14/16
> substitution reservations are **not production English limits**. The canonical register
> is `VWF_BUDGETS.md`. Non-cinematic dialogue now stages **30 source glyphs** on the same
> measured 144px canvas; `wrap_en.py --apply` reflowed all 516 prose-draft rows against
> both limits. Item rows admit 18 source glyphs / 128px including suffix, while item help,
> equipment seals, and the newly converted 40-row clear-condition list use 21 glyphs /
> 144px. Menu and structured rows remain shape/field-specific. Cinematic contracts are
> complete and deliberately untouched.
>
> `fontaudit.py` now classifies every translated manifest class: **0 unproven geometries**.
> The eight bank-11 place labels are selected at `4:$6941-$698B`, staged at `$C62D`, and
> drawn in save-summary box 26 row 2's measured 8-tile/64px slice; `Dragon's Maw` is
> widest at 63 painted pixels / 64px advance. Clear-condition box 44 (x0,y6,w18, five
> rows) now takes the proportional branch.
> Its widest possible current five need 56/57 primary allocator tiles; the permanent
> `conditionspill.py` test drives the real handler, descriptor, allocator, queue, tilemap
> and bitplanes with those five plus an exact 21-glyph fixture.
>
> Two former clear-condition strings used raw `$B1` as a native full-width percent. `$B1`
> has no proportional metadata slot and bank 32 had only three bytes free at that decision,
> so pretending it was supported would be unsafe. The corrected Ground classifier now
> uses the final byte: menu VWF ends exactly at `$8000`, with **zero tail bytes free**.
> The canonical wording is now `Max Belly 200` / `Belly 10
> or less`; the raw unsupported tile is gone. Remaining known review work is concrete, not
> speculative: every signed True Rapier Stepped variant now fits the exact 144px edge;
> visual pacing review is needed after the permissive reflow, and `<var>/<cE3>` producer-to-template
> census remains open. Menu-box shrinking is later V4 polish.
>
> The pre-rescue budget-reset ROM was SHA-256
> `eecd76dfe4a34194378491977418967c00cedf66dff42ebfa0f5fda0509b3816`; the current hash is
> in the closure block above.
> Normal and shuffled builds both pass composer timing/upload, 0/20,320 text-spill frames,
> hostile/menu/help/seal/condition/ROM/start/rank/structured/new-game checks, and separate
> dungeon plus town crash sweeps of 12 seeds × 20,000 frames with 0 halts. The seeded
> message-duration run now sees 11 boxes after permissive reflow; that is pacing-review
> input, not a failure or a reason to restore speculative headroom.

> ## CURRENT — BLANK SCROLL SLOT CLASSIFIED UNUSED, 2026-08-10
>
> The item-name table contains `はくしのまきもの` / `Blank Scroll` at
> `11:$43B2`, zero-based item ID `$66`, but that does **not** make it obtainable or
> functional in this GB release. Bank 6 `$5CE0` scans the canonical object table and sets
> byte 1 to `$FF` for item `$66`; `tools/mesen_spawn_blank_scroll.lua` now injects exactly
> that reset-state record through the real SRAM inventory/object structures.
>
> The corrected object still offers only `Read / Toss / Drop / Info`. `Info` reuses the
> Lost Scroll description, and `Read` consumes the object without opening a writing screen
> or producing a useful effect. The dormant bank-30 `かく` (`Write`) verb has no category-table
> entry and no reachable code path. This is leftover item data, not a missing translation
> route: there is no Blank Scroll keyboard, prose, or VWF screen to implement. Keep the Lua
> helper only as a documented unused-item probe; do not add Blank Scroll work to V4 or V5.

> ## CURRENT — NAME-ENTRY GRID CLEANUP COMPLETE, 2026-08-10
>
> The deferred Session 3b zero-byte cleanup is done. Box 12 retains its five 18-cell rows
> and the picker's three selectable blocks at columns 0-4, 6-10 and 13-17, but their
> contents now flow continuously with no accidental selectable gaps:
>
> ```text
> ABCDE | Zabcd | yz.,'
> FGHIJ | efghi | -!?()
> KLMNO | jklmn | :/[]+
> PQRST | opqrs | 01234
> UVWXY | tuvwx | 56789
> ```
>
> Box 13 remains aliased to box 12; its 116-byte free run is still owned by the bank-31
> layout, and both internal page branches select the same visible characters. Box 12 is
> now explicitly excluded from DTE because the drawer could expand a pair but the picker
> returns one raw ROM byte. `gridprobe.py` derives the relocated row base from the built
> instruction, rejects a route with zero observations, and passes every row on both page
> branches in normal and shuffled builds. Fresh `Shiren`, Rename `Keyaki`, save/reload,
> `newgamesmoke`, the fixed-cell control comparison and the full build battery are green.
>
> Joey's Copy Log -> Erase copied log -> New Log route exposed one additional lifetime
> boundary: the Erase confirmation borrows native tile `$89` for `Log of Shiren` and
> `$9E-$A0` for `Erase this?`, while name entry needs those IDs for its field underline
> and fixed-cell `(`, `)` and `:` keys. Both New Log and Rename now restore all four
> native planes atomically before initializing the name screen. `nameflowspill.py`
> follows the complete supplied-save route and requires its settled pixels, visible
> shadow and cursor positions to match fresh entry exactly; normal and shuffled builds
> pass.

> ## CURRENT — V4D BOUNDED COMPLETENESS AUDIT COMPLETE, 2026-08-10
>
> All ten script-bank `coverage.py` embedded/unframed hits have been traced to their
> consumers. Six are fragments of pointer tables (`4:$514F`, `11:$45E6`, `11:$5067`, and
> three runs in the item-help table at `13:$554A-$5683`); `4:$5285` is executable code
> that copies a 5x8 graphic into VRAM; `30:$7884` and `31:$689E` are graphics/frame data;
> and `3:$7F64` is inside a 16-byte animation/state record table. None is text.
>
> `tools/coverage.py` no longer accepts an unexplained baseline count. Each false positive
> requires the reviewed address, exact bytes and structural reason; any new or byte-changed
> script-bank hit fails. This closes the bounded V4D candidate audit. Broader discovery of
> unknown runtime entries remains ongoing playtest intake in V4B and a required V6 route
> sweep, because no static byte census can prove that an event never starts inside an
> already covered record. That open-ended discovery is not a blocker before V5.

> ## CURRENT ROADMAP — START HERE
>
> Joey is broad-playtesting the current build while this sequence begins. Record every
> screenshot and exact route immediately, but batch related edits into the session that
> owns them so a wording fix is not mistaken for a renderer fix. **Do not reopen the
> cinematic VM:** its separate measured contracts and approved playback are complete.
>
> 1. **V4A — OPTIONAL AUDIT; NO KNOWN FIT FAILURE.** `fontaudit` currently reports zero
>    definite physical/source failures, zero unproven translated renderer classes and 28
>    explicitly historical 14/16 substitution warnings. The signed True Rapier case
>    is already closed. A producer-to-template census could replace those review labels
>    with exact value classes, but it is research rather than a demonstrated repair and
>    is not a release blocker. **Never shorten or mass-rewrite translations merely to
>    silence these warnings.** Resume V4A only for an explicitly requested census or a
>    concrete playtest value/route that fails; fix only that proven failure.
> 2. **V4B — concrete playtest/text intake; scope intentionally open.** There is no
>    predeclared bulk rewrite. Place Joey's next suggested work here when it concerns
>    wording, authored line breaks, spacing, pacing, reveal rhythm or a newly observed
>    hidden-text route. Concrete regressions on closed menu routes retain V4E/V4F ownership.
>    Preserve the distinct Nagi-rescue dialogue and the shared ordinary-stair choice.
>    Any glyph/advance edit must rerun every pixel,
>    tile-allocation and hostile-variant audit.
> 3. **V4C — menu geometry polish (COMPLETE; VISUALLY APPROVED 2026-08-10).** The
>    measured shrink, normal/shuffled engineering battery and Joey's in-emulator review
>    are complete; see the current V4C block above for exact restored boxes and four
>    categories that retain one extra cell. Keep intentional fixed fields fixed: status
>    values, Fay task/stars, and the now-cleaned-up name keyboard are not missed VWF.
> 4. **V4D — translated-text completeness audit (COMPLETE, 2026-08-10).** All ten static
>    script-bank embedded/unframed candidates are non-text and exact-byte classified in
>    `coverage.py`; the structural evidence is in `FINDINGS.md`. Strict `gbrun --dte-scan`
>    remains the response to supplied routes and the Nagi-rescue `$5AFD/$5B81/$70BE` entries
>    remain the model, but open-ended route discovery now lives in V4B/V6 rather than
>    keeping this bounded audit perpetually open.
> 5. **V4E — starting-menu atomic clearing and Rankings ownership COMPLETE.**
>    Title, Log selector, summary, confirmation, difficulty and Rank/Pass redraws publish
>    only complete shadow maps; Rankings rebuilds behind a blank alternate map; Fay's task
>    screen restores every borrowed plane before reveal. `mainmenuspill`, `startspill`,
>    `rankspill` and `structspill` cover the real supplied-save routes on normal, shuffled
>    and redirect-all layouts. Rankings' unified `$80-$A6` board allocation, temporary
>    `$C0-$CB` selector allocation and native reload now make the single-bank lifetime
>    explicit; `orochisymbolspill.py` covers the adjacent Adventure Log owner.
> 6. **V4F — item-menu stale-text and page-transition repair — COMPLETE; VISUALLY
>    APPROVED 2026-08-10.** Exact item entry/paging and the three Wood Arrow
>    action/Info transitions use `old -> white -> complete` transactions. Gitan's shorter
>    three-choice action box also returns safely after its one-page Info text. Saved
>    normal/shuffled/redirect-all routes have zero mixed frames and preserve compact
>    geometry, native cursors, page indicators, allocator ownership and item/action/help
>    VWF. Box 14 composes all of `Items` and its spacing is visually approved.
> 7. **V5 — graphics — COMPLETE, split into four independently approved phases.** These are graphical
>    assets/paths, not a reason to reopen the completed `intro.tsv` cinematic renderer:
>    **V5A COMPLETE** pre-intro title/copyright card; **V5B COMPLETE** illustrated title
>    screen; **V5C COMPLETE** dungeon and town markers/screens (including the floor-name
>    banner); **V5D COMPLETE** all 22 native ending-credit cards, with the final Japanese
>    end mark preserved.
> 8. **R3 — Rankings VWF ownership — COMPLETE; VISUALLY APPROVED 2026-08-12.** Automated
>    normal/shuffled/redirect-all and both LCD execution modes pass, and Joey approved the
>    exact repeated Mesen route in `docs/archive/HANDOFF_RANKVWF.md`; VWF remains mandatory.
> 9. **V6 — release-candidate freeze.** Freeze font, text, graphics and box geometry; run
>    the complete normal/shuffled battery, the 48-run dungeon/town crash sweep and intro
>    regression; perform a clean translator workflow dry run from editable TSVs through
>    `build.sh`; then update final hashes, README/handoffs and release/commit notes.
>
> With V4C/V4F, V5, the name grid, Blank Scroll question and both supplied rescue
> regressions and R3 closed, no known renderer or gameplay blocker remains.
> **V5D is complete and save-regressed.** V4B remains an
> ongoing intake lane rather than a scheduled bulk pass, and V4A remains optional research.
> Continue the broad playtest and proceed to V6.
>
> Do not schedule V4A merely because the 28 historical warnings remain. New screenshots
> belong in V4B's intake unless they expose a crash, progression blocker, concrete runtime
> substitution failure or clearly missing renderer. V4E and V4F are closed; reopen either
> only for a concrete regression on its owned route. Investigate exact routes without
> broad translation rewrites.

> **VWF EVERYWHERE — V3 ENGINEERING COMPLETE 2026-08-09; BROAD PLAYTEST UNDERWAY.** The
> approved Thin Pixel-7 GB Compact proportional path now covers dialogue; WRAM-staged
> main/item/action rows; item information and seals; 19 measured ROM-sourced menu boxes;
> title/file/difficulty flow; the rankings-list writer; and both programs of the cinematic
> VM (boot prologue and post-game ending). `script/intro.tsv` is canonical and normal
> builds consume it. V1 remains
> closed: box-45 Rank/Pass and box-27 Log 2/3 are guarded and the expanded `startspill`
> passes 84 exact rows / 16,182 live checks on normal and shuffled builds.
>
> V2's production check is `python3 tools/introspill.py build/_base_expanded.gb
> build/shiren_en.gb --png-dir build/introspill_latest`. It passes 11 translator-facing
> round-trip/edit/error checks, both complete VM variants, all 12 Dot packs, 70 exact native
> VBlank passes, ten full-pause pixel-stability checks, exact settled shadow rows and blank
> overlay rows, exact original pause lengths,
> natural returns, and both early/active-pause input/skip behavior. `newgamesmoke` still
> reaches the village from blank cartridge RAM. Joey approved the complete prologue and
> forced ending playback in emulator on 2026-08-09. `python3 tools/introplayback.py`
> reproducibly records that ending from the current built ROM without a completed save.
> **V3 now has an explicit measured policy and a green normal/shuffled battery; its
> engineering gate is closed. Broad playtest findings feed the scoped V4 work, and V4C
> menu geometry is visually approved and complete.**
> If this session is about menus, fonts, or anything
> drawn by bank 31's box drawer, read that file first — its §4/§4B record EIGHT ROM facts
> (the `$C006` queue's 9-tile pass, the one-cell park stomp, the six glyph tiles inside
> $40-$7F, the shape-dependent raw prefix, the box-25 hazard, ...) that FINDINGS and
> HANDOFF_VWF do not have. Session 11 now has a completion block above its historical
> research; the historical Session 10 graphics brief now feeds V5A-V5D.

> ## V3 STRUCTURED FIXED-CELL POLICY — IMPLEMENTED; ENGINEERING GATE CLOSED
>
> V3 did not turn cursor tables and absolute numeric writers into prose. Live measurement
> split the four targets by ownership:
>
> * **Status values stay fixed-cell:** bank 4 writes Gitan/Floor/Path values, `G`/`F`, and
>   the difficulty (`Easy` / `Normal` / `Hard`) into absolute aligned cells. Moving those
>   fields would discard useful alignment and fight the writer. The static box-2 words
>   **`Weapon`, `Shield`, `Str`, `Exp` now use fixed-position Dot Gothic fragments** while
>   the divider and every value cell remain byte-identical to a `--no-structvwf` control.
> * **Fay's static `No` and `Rating` now use fixed-position Dot fragments.** Task-number
>   cell 4 and star cells 13+ remain game-owned. Both sources are patched: box 30 on entry
>   and the pre-rendered bank-4 row at `4:$704E` used after a task change.
> * **The name keyboard stays fixed-cell by design.** `31:$4186+` computes a character
>   address from cursor row/column and a row stride. One cell is one selectable character;
>   proportional spacing would make the visible grid disagree with its lookup table. The
>   visible English grid is now cleanly ordered; the old kana page is aliased, unrendered
>   storage rather than being mislabelled as missed VWF.
>
> `tools/structvwf.py` installs the fragments after `menuvwf`; `--no-structvwf` builds the
> matching control. The complete control BG/window/OBJ census supplied the 18 source slots.
> `$87` was rejected after the broad census found screen-24 use. `$D1-$D6` were rejected
> after the real Fay screen rewrote their planes. Three final IDs (`$94/$95/$9D`) are
> context-shared with the dynamic allocator: `menuspill` admits them only at the exact
> status/Fay cells and only while their live planes equal the approved raster, preserving
> the hostile inventory peak at 71/72 tiles.
>
> `tools/structspill.py` is the acceptance test. It checks both status rows and all custom
> planes, takes the **real blank-cart route** to Fay (a forced dispatcher was measured and
> rejected because it never installs the input callback), changes task 1→6, requires
> `4:$700E` to fire, checks the bank-4 redraw's BG map and dynamic number/star parity, and
> requires the fresh name keyboard to be pixel/shadow identical to the control. Normal and
> shuffled runs report 0 problems. The broader menu/start/rank/new-game/intro/logicdiff
> batteries also pass normal and shuffled, and crashscan reports 0 halts across 2 ROMs ×
> 12 seeds × 20,000 frames. That V3 snapshot is superseded by the current budget-reset ROM
> and hash at the top of this file. Review images are
> in `build/structvwf/`: compare
> `status_control.png`→`status_vwf.png`, then `fei_control.png`→`fei_vwf.png` and
> `fei_vwf_redraw.png`. After Joey approves those screens, mark V3 visually closed and
> begin V4 spacing/box-size polish.

> ## CINEMATIC VM — COMPLETE AND VISUALLY APPROVED
>
> The measured programs are actually `31:$5C62-$5DBD` (348 bytes) and
> `31:$5DBE-$5FA8` (491 bytes), not the older `$5C63-$5FA0` estimate. `tools/intro.py`
> hashes and parses both with the measured arities (`$4D:1`, `$4E:2`, `$4F/$50:3`,
> `$51:1`, `$52/$54/$55:0`, `$53:6`), extracts 33 translatable plus four decorative
> text runs into 12 canonical TSV rows, validates source metadata, wraps English by Dot
> Gothic pixel width, and installs relocated programs plus 12 static VWF packs in reserved
> bank 63. The original typewriter reveals proportional 8-pixel slices. One private period
> tile preserves program 1's three staggered dramatic dots.
> Program 0 is the boot/title prologue. Program 1 is not another attract-mode opening:
> it is the post-game ending after clearing floor 49 of Moonshadow Village Exit. A measured
> 100,000-frame idle-title run repeated program 0 nineteen times and never selected program
> 1; `introspill` deliberately forces the ending object's variant byte for practical review.
>
> **Joey's first visual run found a real V2 defect:** one caption rendered correctly, then
> turned into a white/corrupt block while the next pack uploaded, alternating for the whole
> sequence. The first candidate used one `$8B10` tile buffer and rewrote it while the
> outgoing tilemap still referenced it. Joey's next run found a second measured defect:
> the stable `tradition` caption was split across the blank overlay row. Raw cinematic
> codes `$45/$46` are dakuten/handakuten overlay marks, not advancing glyph cells; treating
> them as ordinary VWF slices made odd packs overwrite their live overlay tiles. The final
> allocator preserves `$45/$46`, reserves code `$4C`/tile `$FC` for the panel fill, and
> splits the 73 ordinary codes into two disjoint buffers: even screens `$01-$22` (34 tiles
> at `$8B10`) and odd screens `$23-$44` (34 tiles at `$8D30`) plus `$47-$4B` (five tiles at
> `$8F70`). The fragmented odd buffer deliberately skips overlay VRAM `$8F50/$8F60`.
>
> Hidden packs start one tick into each existing 30-200-frame pre-clear pause. Seven
> 100-byte passes reuse mode `$08`'s five native records at `$C006/$C01C/$C032/$C048/$C05E`;
> this does not add work to the VBlank handler. The records remain parked as self-copies
> for the rest of the pause, then their native tilemap destinations are restored on the
> terminal delay tick before the clear repopulates their payloads. This final restore is
> load-bearing: parking destinations without restoring them caused every odd caption to
> remain blank until the next even-buffer upload. Delay arguments and clear opcodes are
> unchanged. Each pass now carries five independent 20-byte destinations rather than
> assuming one contiguous target, which makes the fragmented odd buffer safe. `introspill`
> proves source and
> English pause lengths `60/100/160/60/60` and `30/140/200/60/50`, all packs present in
> VRAM before clear, source/English returns at frames `3040/3024` and `4269/4260`, clip-0
> A-skip at frame 1012 in both, active-pause skip parity, all ten outgoing panels unchanged
> on every pre-clear frame, all settled native shadow rows and blank overlay rows exact,
> and clip 1's original unskippable behavior in both. That row oracle specifically catches
> stable pre-pause corruption such as the old `tradition` split, which pixel-stability alone
> could not. Joey's revised villager caption fits the full 39/39 safe odd-screen tiles; the
> following narration is reflowed over its three measured lines as `A small village was
> said to` / `offer children` / `as sacrifices to a monster.`
> Joey approved the prologue and ending panels on 2026-08-09. The ending rewrite is measured as:
> `Koppa: Phew, we finally got out.`; `Look, over there!`; `I can see Mount Sasara!`;
> `I don't think they'll ever drag` / `us back again.`; `Koppa: You mean Keyaki? She`
> / `was such a sweet, brave girl...`; `Koppa: ...It can't be helped.` / `We're wanderers,
> after all.`; and `Come on, let's go!`. Its tight pools are 34/34 and 37/39 tiles.
> `coverage.py` now reports the third alphabet separately and gates all 37 runs. The
> approved V2 ROM SHA-256 is
> `9548bf505153f2ce1c49593bdd6361f27a68e02c3f4a16f09e2a400b5b536e93`.
> The final static/runtime battery passes on normal and shuffled layouts: dialogue,
> menu, title/save, rankings, new-game and intro emulator checks are green, and all 48
> 20,000-frame dungeon/town crash runs complete with zero halts.
>
> ## HISTORICAL DISCOVERY — ~~"THE SCRIPT IS FINISHED"~~ WAS RETRACTED 2026-08-06
>
> The **opening cinematic was untranslated**, and it is the first thing a player sees. It was
> never in `script.json`, so `coverage.py` — the check written in session 7 *specifically*
> to answer "is what we extracted all there is" — reported zero missing and was not lying.
> It reads bytes through `codec.py`'s table, **and the cinematic uses a different one.**
>
> **A THIRD character encoding, and the tool that was built to find missing text cannot see
> it.** The cinematic is a bytecode program at `31:$5C63`-`$5FA0` whose text bytes are
> indices into a 77-entry translation table at **`13:$7FAA`** — space, あ-ん, っゃょ, the 17
> katakana the game owns, ！？, the dakuten pair, 「」・、。 — densely packed, so `あ` is `$01`
> and not `$0B`. Under `codec`'s table those bytes decode as unrelated kana, which is why
> nothing flagged them: **it is not that the region scored badly, it is that it scored fine
> and said the wrong words.** Session 7's gap was one stale table, 8b's was one dispatch
> table applied to two paths; this is the same family and the third instance.
>
> **Session 9's session-order banner said the next session was 10. It is now 11 — see §3.**
> The graphics brief is unchanged and still correct; it is simply not first any more.

> ## THE PLAN CHANGED ON 2026-08-05. READ THIS BEFORE ANYTHING ELSE.
>
> ~~"The engineering is DONE — everything left is translation."~~ **That was wrong**, and it
> was wrong in the two ways that matter most, both found by **Joey playing the build** rather
> than by any check in this file:
>
> **1. ~~The text box is broken for long lines.~~ FIXED 2026-08-05, sessions 6 and 6b.** Two
> defects, both found by Joey playing and neither visible to any check here. The typewriter
> revealed one tilemap cell per CHARACTER, so a line over 18 characters drew the next line's
> start at its right edge — at a 6px pen a character lives in tile `(6N+5)>>3`. And a
> trailing `<end>` drew the last box a SECOND time, costing a button press per message.
> `tools/boxspill.py` and `lint_en`'s `end_trailing` are the two checks that were missing.
>
> **2. ~~We do not have all the text.~~ FIXED 2026-08-05, sessions 7 and 8b — TWO causes,
> both a rule that ignored a difference between two things.** `script.json` held
> ~8.0 KB less dialogue than banks 11 and 14 contain. **It was one stale table.**
> `regions.py` built its idea of "a text byte" from `textdump.py`, the day-one exploratory
> decoder, instead of from `codec.py` — so it was missing 39 byte values, among them
> `<brk>` (120 uses in bank 14), `、` (110), `<cEC>` (47) and `『』（）：`. Those are ~2% of a
> prose block and `script_regions` demands 97%, so every block of the shop, the
> monster-house warning and the Kuyo Pass road picker scored 0.90–0.97 while being 48–71%
> kana. The region never opened, and the block walker only walks open regions.
>
> **1261 → 1404 strings, 28,646 → 36,821 script bytes.** All 143 new strings are in banks
> 11 and 14. `tools/coverage.py` is the check that was missing; it is in §1 and in
> `build.sh`.
>
> **A SECOND CAUSE was found after this and is also fixed — session 8b, same day.** 532 more
> bytes, including the shop's opening line and the ending narration. Same shape of bug: a
> rule derived from one dispatch path and applied to both. `extract.impossible()` rejected
> any block containing `$F1-$FE` because bank 13's table at `13:$4126` has 17 entries — but
> banks 11/14 dispatch through `13:$68CF`, which has **21**. `$F1-$F4` are ordinary control
> codes there. **1404 → 1419 strings.**
>
> **Joey raised (2) before and was given an answer instead of a measurement.** The reason it
> could not be answered is that **nothing in this project had ever measured extraction
> coverage** — the battery checked that what we extracted round-trips, never that what we
> extracted is all there is. `1261 strings` was never a total; it is what the extractor
> happened to find.
>
> **3. ~~A translated string reads English on screen.~~ FIXED 2026-08-06, session A1 — and
> this is the one to carry forward.** 25 strings were 100% translated, round-tripped
> through the pool byte-perfect, and passed every check in §1, and **a player saw one
> Japanese glyph**. The defect was not in the text at all: `13:$6C73` re-derives the resume
> POINTER as "the address the message came from, plus 2" for every `<cEC>` string, which
> after a redirect lands in the middle of the 4-byte record. Among the 25 was the Kuyo Pass
> road picker Joey had reported for several sessions.
>
> **`script.json` says what we STORED, not what a player READS.** Sessions 7 and 8b closed
> the gap between "extracted" and "exists"; this one opened a gap between "translated" and
> "rendered", and nothing in §1 could see it — every check compared the build against a
> model of the text, and the text was right. `tools/msgshot.py` is the answer: it draws any
> bank-11/14 message on the real screen, so a screen no walk reaches can still be
> photographed. **Photograph the screen, not the string.**
>
> **~~Bulk translation is paused until session 7 lands.~~ UNPAUSED 2026-08-05.** Session 5's
> 355 translations survived intact, and that was verified rather than assumed: zero `loc`
> keys lost, no surviving string's Japanese changed, and `wrap_en.py --apply` reproduced
> `en.tsv` byte-identical.

Read §0 and §1, then start at the first session in §3 that is not struck through.

```
  DONE   0  space            1  name 4->6        1b rankings 4->6
         1c save states      2  VWF 18->24 cells
         3  the glossary -- 391 names frozen in script/glossary.tsv, lint enforces them
        3c  item verbs Drink/Equip/Remove; the [N] counter budget
         4  bank 13 -- 341 strings. BANK 13 IS DONE END TO END
        3d  weapon/shield names aligned to Shiren 6; every one is now <= 14 cells
         5  village and story prose -- 355 strings, for what was extracted
         6  the column-19 spill -- FIXED. tools/boxspill.py joins the battery
        6b  the trailing <end> that drew a box twice -- FIXED. lint_en `end_trailing`
         7  EXTRACTION COMPLETENESS -- FIXED. regions.py duplicated codec's table and it
            had gone stale. 1261 -> 1404 strings. tools/coverage.py joins the battery
        8b  the other 532 bytes -- FIXED. impossible() used bank 13's 17-entry dispatch
            table for banks 11/14, whose table has 21. 1404 -> 1419 strings
         8  TRANSLATED -- 161 strings. The shop, the Shrine Priest's help, the Kuyo Pass
            road picker, the well, Dragon's Maw, the feast and the farewells.
            1212 -> 1373. Bank 14 is 334/335, bank 11 623/643
      pre8  codec.ARITY hid a real character inside <cF0> in banks 11/14 -- MEASURED and
            fixed before translating. Third instance of the same shape of bug

       8c  BOX 48 IS TRANSLATABLE -- the "Normal" difficulty text Joey reported. It was
            never the byte arithmetic; extraction PINNED the box by mistake. Boxes 50
            and 51 came free with it. 1373 -> 1376. Fei's Quiz header done too

       A2  Fei's Quiz header -- FIXED. A second copy at 4:$704E, a pre-rendered
            tilemap row; build.py now MIRRORS box 30's translation into it

       A1  the town signs -- FIXED 2026-08-06. NOT the geometry: the REDIRECT. 13:$6C73
            re-derives the resume pointer as "original + 2" for every <cEC> string and
            landed in the middle of the 4-byte record. 25 strings, not 6 -- including
            the Kuyo Pass road picker Joey has reported for several sessions.
            tools/msgshot.py + saves/sign.state join the toolkit

        9  the weapon/shield SEALS -- 20 strings, DONE 2026-08-06. Bank 11 is 643/643.
            The budget was 18 cells and ONE line, not 4: a seal IS a row, and 11:$7E40
            copies four of them under the item name. NOTHING had been measuring them --
            is_help() was scoped to bank 13 AND is_dialogue() returned False, so both
            build.py and --check skipped them entirely. All 20 PHOTOGRAPHED:
            tools/sealshot.py joins the toolkit, build/seals_*.png are the screens

       V1  VWF MENU GAPS -- CLOSED 2026-08-08. Box 45 Rank/Pass and box 27 Log 2/3
            confirmation are proportional and guarded; normal/shuffled acceptance passed.
  DONE  11  PROLOGUE/ENDING CINEMATIC VM -- canonical `script/intro.tsv`, proportional VWF, both
            programs and third-alphabet coverage implemented and visually approved.
            See the current block above and session 11 below.
  DONE  V3  structured fixed-cell policy and measured proportional budget are battery-green:
            box-2 and Fay's static words use font fragments; aligned status values and
            selectable name cells remain fixed. Broad playtest now feeds V4B.
  DONE  3b  visible name grid reordered without gaps; both aliased page branches and
            fresh/rename/save paths pass on normal and shuffled layouts.
  DONE  V4C  compact menu geometry, cursor coordination and normal/shuffled batteries;
             visually approved by Joey 2026-08-10.
        V4A  optional `<var>/<cE3>` producer research; no demonstrated fit failure.
  OPEN  V4B  concrete playtest/text intake; Joey's next proposed work may define it.
  DONE  V4D  ten static embedded/unframed candidates classified non-text by exact bytes;
             unknown runtime-entry discovery remains ordinary V4B/V6 route QA.
  DONE  V4E  starting-menu, difficulty, Rank/Pass, Rankings and Fay transition clearing;
             Rankings also has screen-scoped one-bank ownership and native restoration.
  DONE  V4F  inventory/header, Wood Arrow Floor/Info and Gitan three-choice Info-return
             transitions visually approved or save-regressed.
 CLOSED  R1  Blank Scroll `$66` is unused GB data: no Write route or scribing screen.
  DONE  V5A  Joey's full-screen Shiren GB / ©1996 Chunsoft / ©1996 Koichi Sugiyama
             pixel mock-up; exact 160x144 raster with native palette, fade/timing,
             input path and scene-0 transition retained.
  DONE  V5B  viewer-supplied four-colour Mystery Dungeon / Shiren / The Wanderer /
             Monster of Moonlight Village / GB title; exact 160x144 map and file-menu
             transition. This supersedes the earlier approved title asset.
  DONE  V5C  all eight dungeon/town arrival labels use the approved 12px-cap Poppins
             treatment; Moonlight Village and Forest 1 are reference-exact, and every
             stored form plus all 50 live floor values is runtime-exact.
  DONE  K1   bank-13 stair loads retain cross-bank `14:$46C1` (`Go down / Stay here`);
             two Koppa floors plus Nagi and Fumi are save-regressed.
  DONE  K2   shared rescued-child final exit: LCD-off Rankings rows now upload
             synchronously; Nagi Log-1 exit save reaches the live result screen.
  DONE  R3   screen-scoped proportional renderer, automated matrix and Joey's exact
             Kuyo/repeat/Village Exit Mesen route all pass.
  DONE  V5D  all 22 native ending-credit cards translated in the approved Poppins
             white/green style; native order/durations and Japanese End mark preserved;
             real Hard-ending save proves the complete roll and post-credit transition.
PENDING V6   release-candidate freeze after the broad playtest. Historical
             Session 10 below is the graphics brief, not a separate roadmap phase.

  DONE  3e  signed/count item suffixes are exhaustively linted; cursed and plated markers
            have a real-save proportional regression.
```

> ### ~~SESSION 7 — `extract.py` MISSES ~8 KB~~ — **DONE 2026-08-05. It was a DUPLICATED TABLE.**
>
> **`regions.py` restated `codec.py`'s character table instead of importing it, and the copy
> went stale.** It was built from `textdump.py` — the day-one exploratory decoder, whose
> table never grew past kana, digits, space and `ー` — while `codec.py` spent the whole
> project gaining the punctuation block, the bracket pairs, the second digit set, the Latin
> stat letters and 5 of the 17 control codes. **39 byte values in total.**
>
> Those bytes are only ~2% of a prose block. `script_regions` requires 97% recognised bytes,
> so ~2% unrecognised is *exactly* enough to hold a block of real dialogue under the bar.
> Every 128-byte block in bank 14's shop scored 0.90–0.97 while being 48–71% kana — the kana
> test, the one that actually looks for prose, passed everywhere and was never the problem.
>
> **Nothing else could have rescued them, and this is the part worth remembering.** The
> extractor has exactly three discovery mechanisms: pointer tables, the menu-box table, and
> the region walker. `immediate_refs` looks like a fourth and is not — it matches operands
> against strings *already found*, so it can annotate a string but never discover one. Once
> the region failed to open, the text was unreachable by every path.
>
> `regions.py`'s docstring said *"Computed rather than hardcoded, so it stays correct as the
> table improves."* It was computed — from the wrong table. Both halves of a duplicated
> table can be honest and the pair still drifts.
>
> **A second, smaller cause, found after the first was fixed:** `min_size=0x180` discarded a
> 256-byte island holding the shop's five money lines, because the price-entry digit strip
> between it and the main region is 100% script bytes but only 34% kana. `script_regions`
> now BRIDGES a pure-script block that real text brackets on both sides. Lowering `min_size`
> instead was measured and rejected — it buys those 5 strings and 8 pieces of junk,
> including a 198-byte kerning table in bank 29, a bank `logicdiff` does not guard.
>
> **Result: 1261 → 1404 strings, 28,646 → 36,821 script bytes.** All 143 new strings are in
> banks 11 and 14. Four junk strings that came with the widened regions are declared in
> `extract.MANUAL_DROP` — `3:$7580` is the same `ld [$FF91],a` idiom as the long-standing
> `6:$472F`, its `$FF` operand byte read as a terminator.
>
> **What it cost elsewhere, and both are worth reading before trusting a budget again:**
>
> * **`dte_rom.DTE_RANGES` was invalid and the build caught it.** The code space is "bytes
>   untranslated Japanese never uses", measured against `script.json` — so an incomplete
>   `script.json` silently invalidates it. `$C8` and `$DC` are `$EB` typewriter-pause
>   arguments in the ending farewells, which had never been extracted. Re-measured, 46 codes
>   → 32. The top range must abut `$E0` (the last range emits no upper compare), so `$DC`
>   caps it at `$DD-$DF` and the 19-code run `$C9-$DB` has to be spent as a middle range.
> * **`dialogue_preview --selftest` fired on seven new lines**, all the same `$EB` case that
>   was hand-listed for `14:$56EF`. It is now a RULE rather than eight allowlist entries,
>   and the evidence it is a rule is that every over-long line lands on **exactly 18** once
>   its `$EB` count comes off — 19−1, 20−2, 21−3. The model then passed on 1,704 Japanese
>   lines, several hundred of which it had never seen, with the same cliff at 18 (278 lines
>   exactly on it). That is the strongest confirmation available that the new strings are
>   genuine text with correct boundaries.
>
> Session 5's 355 translations survived, verified not assumed: zero `loc` keys lost, no
> surviving string's Japanese changed, `wrap_en.py --apply` reproduced `en.tsv`
> byte-identical, and `logicdiff.py` still reports banks 7/8/9/10/12 untouched.
>
> **A SECOND CAUSE, found immediately after and fixed the same day — session 8b below.**
> The first version of `coverage.py` reported zero and was wrong: it only looked at
> `$FF`-delimited runs whose every byte decodes, and the shop's opening line is not framed
> that way. Scanning STRETCHES instead surfaced 22 more runs, **12 of them real prose,
> 532 bytes**.

> ### ~~SESSION 8b — TEXT INLINE IN AN EVENT BYTECODE~~ — **DONE 2026-08-05. There was no bytecode.**
>
> **12 runs, 532 bytes** — the shop's opening line (`14:$4031`), Yoshizota's confession
> (`14:$4CA4`, 98 bytes), the ending narration (`14:$4FE0`), Kinji, Keyaki at the shrine,
> Fumi calling for her mother (`11:$56C3`), the feast narration (`11:$5E90`), and
> `<name>は かぜにとばされた` (`14:$46EE`), which Joey had seen on screen as gibberish.
>
> **IT WAS ONE RULE, AND THE SAME SHAPE OF BUG AS SESSION 7 — a rule derived from one of
> two things and applied to both.** `extract.impossible()` rejected any string containing
> `$F1-$FE`, reasoning that the dispatch table has exactly 17 entries so such a byte would
> index past it and jump to garbage. True of `13:$4126`, the bank-13 MESSAGE path. **Banks
> 11 and 14 dispatch through `13:$68CF`, and that table has 21 entries, `$E0-$F4`**:
>
> ```
> 13:$4126  message  (bank 13)      17 entries, $E0-$F0.  entry 18 = $F5C9, garbage
> 13:$68CF  dialogue (banks 11/14)  21 entries, $E0-$F4.  entry 22 = $FAF5, garbage
> ```
>
> `13:$68B3` does `sub $E0 / sla a / add a,$CF` and indexes with **no upper bound**, so
> `$F1-$F4` really dispatch — to `$6A33`, `$6A3E`, `$6A5D`, `$6A55`. All four are ordinary
> handlers in the same idiom as `$EE`/`$EF`, all `ret`-terminated, none reading an argument.
> `$F3`/`$F4` are a matched `res`/`set 7,[$CF8A]` pair exactly as `$E8`/`$EB` are
> `mode0`/`mode1`. They are now `<cF1>`–`<cF4>` in `codec.CONTROL`.
>
> **Why it cost so much more than four codes.** `impossible()` judged the whole
> `$FF`-delimited BLOCK, and in these banks a block is not one string. A single `$F4`
> discarded everything around it: `14:$4C89`'s block is 125 bytes holding two complete
> messages with one `$F4` between them.
>
> **A second, smaller fix was needed: `extract.script_starts_at()`.** Two blocks really do
> have code in front of the text with no terminator between — `14:$401D` ends
> `... <cE1> <$C1> <cF1> <$C9>` and `$C9` is `ret`. Extracting from there would have handed
> the inserter twenty bytes of live code to overwrite the moment anyone translated the
> shop's greeting. The string now restarts after the last byte in `$C0-$DF` that is not a
> control code's argument — **the DTE code space, which `dte_ranges.py` has already proved
> untranslated Japanese never contains**, so it is a measured marker and not a guess. It
> fires exactly twice and lands on the nose both times: `14:$401D` → `14:$4031`
> (`てんしゅ「いらっしゃいませ」`) and `11:$56B2` → `11:$56C3` (`フミ「・・・おかあさん`),
> both of which had been identified by eye first. **It is scoped to banks 11 and 14**:
> applied ROM-wide it also trims data runs in banks 2/3/4/9/29/31 and admits 12 junk
> strings, one of them in bank 9, which `logicdiff` requires to be untouched.
>
> **1404 → 1419 strings, 36,821 → 37,475 bytes.** Zero `loc` keys lost, no surviving
> string's Japanese changed, and `--selftest` now passes on 1,746 Japanese lines with 282
> landing exactly on 18 — 42 lines it had never seen, same cliff.
>
> **What was left in the `embedded` class was 10 runs.** At this session boundary they
> only looked table-like and were protected by a count baseline. The later V4D audit tied
> every run to executable code, pointer tables, graphics or animation records; current
> `coverage.py` requires exact address+byte classifications and fails any unreviewed hit.

> ### ~~SESSION 6 — THE TEXT BOX SPILLS INTO COLUMN 19~~ — **DONE 2026-08-05**
>
> Joey found it in play; `build/boxspill_before_after.png` is the same frame either side of
> the fix. Applied by `tools/vwf.py` (bisect control: `--no-vwf`), 38 bytes at `13:$4418`.
>
> **The writer was `13:$6B59`, the TYPEWRITER, and it is the sixth tilemap writer.** The
> other five all draw a whole row of a fixed 18 (`13:$4523`'s callers) and are all correct,
> which is exactly why reading the row drawers found nothing across two sessions. This one
> reveals ONE CELL A FRAME as the text types: it holds the tile index in `b` and the tilemap
> address in `de`, queues a one-cell write through `13:$6B85` (`[$C000]` destination,
> `[$C002]` tile), then `inc b` / `inc de`. At a fixed-width pen character N *is* tile N;
> at 6px it is not, and past character 17 the count walked into the next line's tiles.
>
> **How it was found, since the last session looked for it and did not get there.** Not by
> disassembly — by diffing WRAM `$C000-$DFFF` frame by frame during a village dialogue and
> looking for a byte that increments once per typed character. `$C000`/`$C002` did, they are
> the one-cell queue, and `13:$6B85` is its only writer. **Two static searches had already
> failed**: every `ld hl,$9Cxx` immediate in the ROM (the address is computed from a table)
> and every "write an incrementing index" loop (this one increments across frames, not
> inside a loop).
>
> **Three things the fix had to get right, and two of them bite if you get them wrong:**
>
> * **Reveal the tile the character ENDS in, `(6N+5)>>3`, not the one it starts in.** The
>   start tile is what the arithmetic reaches for first and it *looks* right; because a 6px
>   character straddles two tiles three times in four, it leaves the tail of the last
>   character on a line permanently hidden — `...Are You all` types out as `...Are You al`.
>   That was measured on screen, not reasoned about.
> * **`b` and `de` go on counting CHARACTERS; only the queued pair is mapped.** The dakuten
>   overlay reads `de - 33`, the cell above the *previous* character, so a `de` that counted
>   cells would move that mark on Japanese lines that render correctly today.
> * **It clamps at 18 cells.** `13:$687B`, the composer the village text goes through, has
>   **no cell budget at all** — the only bound is dte_rom's 49-byte guard at `$CF38`. Nothing
>   in the ROM stops a line at 24 the way `13:$40D6 ld b,$18` stops the other composer's.
>
> **Message timing did not move**, measured against a control that is the shipped ROM with
> only the reveal reverted (`build/prespill.gb`): 10 boxes, total 2539, median 245, min 17,
> max 633 on both. `boxspill.py` goes from **1901 spilling frames to 0** over 20,324 frames
> with text on screen.
>
> **`--no-vwf` fails `boxspill.py`, and that is the control being right.** `en.tsv` is
> wrapped for 24 cells and a fixed-width pen needs 24 tiles for that in a row that has 18, so
> the control really does draw six characters past the end. It is a bisect control for the
> renderer, not a shipping configuration.

> ### SESSION 6b — A TRAILING `<end>` DRAWS THE LAST BOX TWICE (partial fix; see 6c)
>
> *"Press A for the next window, nothing to show, just the same text as before, then press
> again and you get the next one."* He photographed `Fumi's Mom: ...why does it have to be
> my daughter...` appearing twice (`11:$639F`), and confirmed the JP ROM does not do it.
>
> **The defect is a trailing `<end>`, and 59 strings had one.** `wrap_en.py` appended it
> whenever the Japanese's last box waited, on the reasoning that `$CFC4` is tested once so
> *"presence is what matters, not position"*. Presence is what matters WITHIN a box; at the
> end of a string, position is the whole of it. **A/B on one NPC, same save, same frame:**
>
> ```
>   trailing <end>      p1:new   p2:SAME   p3:closed
>   no trailing <end>   p1:new   p2:closed
> ```
>
> **The shipped Japanese never leaves one trailing** — 0 of 820 bank-11/14 strings end with
> `<end>`, and of the 63 whose last box holds one, 32 are followed by `<br>` and 31 by more
> text. The first repair moved the token before the last line/word and added `end_trailing`.
>
> ### SESSION 6c — PRINTABLE TEXT AFTER `<end>` IS UNSAFE TOO. Fixed 2026-08-10
>
> Opening play found the incomplete half of 6b. `11:$6713` displayed *"He went to rescue"*
> instead of *"He went to rescue Fumi!"*, and `11:$67A8` displayed *"I'm not going up"*
> instead of *"I'm not going up there!"*. Pressing A left an unchanged box, then a second
> press advanced. Both rows had the shape `<end> final-word`: the Dot reveal omitted the
> printable suffix but retained the wait.
>
> A full sweep found 59 prose rows produced by the same mechanical last-box policy, 22
> with `<end>` directly before their final word. `wrap_en.py` no longer relocates arbitrary
> Japanese pauses into reflowed English. Existing authored `<brk>` pauses remain; 17
> single-page speeches received explicit semantic `<brk>` positions; and structural
> endings such as `<end><mode0>` remain immediately after all visible text. The new
> `lint_en.end_resumes_text` check fails every build if printable bank-11/14 dialogue ever
> resumes after `<end>` without a `<brk>`.
>
> #### The wrong turning, kept because it cost an hour
>
> The first diagnosis was **box count** — English uses more `<brk>` boxes than the Japanese
> (261 against 120), each costs a press, and `TRANSLATING.md` had actively invited it
> (*"You may add `<brk>` boxes freely"*). All of that is TRUE and it is now measured by
> `tools/boxcount.py`, but **it is not what Joey was reporting**: he said the same text
> twice, and extra boxes show *different* text. The screenshots said so plainly and the
> first reading talked past them. **When a report names a specific symptom, reproduce THAT
> symptom before explaining it** — the probe that settled it took ten minutes and compares
> the 54 line tiles' pixels either side of a press.
>
> **AND THE DETOUR'S OWN FIX WAS ALSO WRONG, which Joey then asked about directly.** The 32
> "SILENT" strings were tightened on the theory that each extra box costs a press. Tested
> head-on afterwards — a two-box and a one-box rendering of the same text in the same NPC,
> counting entries to the wait loop at `13:$541B` — **both are 1 wait and 2 presses. No
> difference.** So 22 of those edits cost real wording and bought nothing, and they are
> **reverted**; the 12 that only dropped a `<brk>` and lost no words are kept, as free.
> `boxcount.py` survives as a PACING report with its press claim retracted, and it is
> **not** in the battery — it measures a preference, not a bug.
>
> **Budget about 62 characters a box, not 72.** Three lines of 24 lose the continuation
> indent and the word breaks, and a `<var>` costs ITEM_CAP 16 rather than its 5 characters.
> Let `wrap_en.py --apply`'s `auto_split` note tell you; do not count by hand.

> ### SESSION 7 — `extract.py` MISSES ~8.0 KB OF DIALOGUE, AND NOTHING MEASURES COVERAGE
>
> **Found 2026-08-05 by playing the build, which is the only thing that ever finds these.**
> Session 5 translated every bank-11/14 string in `script.json` and the battery went green,
> and the game still shows Japanese in the village -- because the text on screen is not
> always the string that was extracted.
>
> **BUILD THE COVERAGE CHECK FIRST, BEFORE TOUCHING `extract.py`.** This is the actual
> deliverable of session 7; the extractor fix is downstream of it. Joey raised this gap in an
> earlier session and got an argument rather than a number, and that was possible only
> because no tool could produce a number. `tools/coverage.py` should:
>
> * walk every bank for `$FF`-terminated runs of pure script bytes that no extracted string
>   covers, and report bytes per bank;
> * classify rather than total — a run carrying `「` or a `<br>`/`<end>`/`<brk>` token is
>   almost certainly dialogue, and that is the number that matters. **Do not report the raw
>   figure**: the naive scan says 33 KB, and 13 KB of that is bank 10's item-stat table
>   decoding as kana by coincidence. Spot-checked 2026-08-05: banks 3, 7, 10 and 29 are all
>   data (`なカなカなカ...`), and only 11 and 14 hold real prose;
> * join §1 and `build.sh`, so the number is on screen every build and can never again be a
>   matter of opinion.
>
> **Then fix the extractor**, re-extract, and re-run the whole battery -- `logicdiff.py`
> especially, since new strings mean new reference candidates and that is exactly how three
> false tables got in before ([[shiren-gb-uniform-table-is-not-a-table]]). Every arena
> budget and projection in §2 has to be re-measured afterwards.
>
> **Session 5's translations survive this.** `en.tsv` is keyed on `loc`, which is stable
> across re-extraction; ids are not, and nothing is keyed on ids. Re-running
> `wrap_en.py --apply` after re-extraction should reproduce `en.tsv` unchanged.
>
> `ニワトリ「コケーッ！」` exists **twice**: at `11:$64EE`, which was extracted and
> translated, and at **`14:$7305`, which was not**. The dungeon reads the second one.
> `14:$46EC` (`<name>は かぜにとばされた`) was never extracted either, and now draws as
> `ShirenZ FNVTZKPP` -- untranslated Japanese through the Latin font, which is what every
> missed string will look like from here on. See `build/session5_village.png`.
>
> **Measured, not estimated.** Scanning banks 11 and 14 for `$FF`-terminated runs of >= 8
> script bytes that no extracted string covers:
>
> | | runs | bytes |
> |---|---|---|
> | carrying `「` or a `<br>`/`<end>`/`<brk>` token -- almost certainly dialogue | **141** | **7,892** |
> | other unextracted runs >= 8 bytes in banks 11/14 | 10 | 192 |
> | for scale: the bank-11/14 Japanese session 5 DID translate | 355 | 20,612 |
>
> So roughly **38% more prose than was translated is still sitting there**, and it is real:
> Fumi crying for her mother (`11:$56C3`), Koppa drunk at the feast (`11:$5C35`-`$5CD2`),
> the Chief on the Kuyo Pass monsters (`11:$5CE2`, 425 bytes), and the ending farewells
> from Fumi and her mother (`11:$5F60`, `11:$5FB6`).
>
> **Bank 14's gap opens at `$4031` and the whole SHOP is inside it** —
> `てんしゅ「いらっしゃいませ」`, `てんしゅ「ありがとうございました」`, the monster-house
> warning at `14:$4176`, and the Kuyo Pass road picker at `14:$4638`/`$465B`/`$467F`.
>
> > **That road picker is the "Normal difficulty is still untranslated" Joey has reported
> > repeatedly.** It was never an explanation string and there was never anything subtle
> > about it: three strings listing all three roads with `（いまえらんでいるみち）` on a
> > different one each, none of them ever extracted. Easy and Hard *look* translated because
> > the menu LABELS are (`31:$441B`/`$4421`/`$4426`); the picker is separate text.
>
> **This is an extraction job before it is a translation job.** Do not hand-add locs to
> `en.tsv`: they are keyed on `loc` and `script.json` is what the pipeline measures,
> redirects and verifies against. Fix `extract.py`, re-extract, re-run the battery, then
> translate the new strings -- `tools/wrap_en.py` and `script/prose_draft.tsv` make that
> last part cheap. Space is not a concern: the pool has 458 KiB free.
>
> **Suspect the extractor's reachability rule, not the bank.** Every one of these runs is
> in a bank the extractor already covers, between strings it already found -- `14:$7305`
> sits between `14:$72EA` and `14:$7518`, both extracted. Related:
> [[shiren-gb-extraction-heuristics]].

> ~~**READ THIS BEFORE TRANSLATING `11:$5803`.**~~ **CLOSED 2026-08-04.** The latent
> `BADREF` at `11:$5848` is gone: the "table" keeping it alive, `9:$6FCD`, was a four-byte
> record structure read at a two-byte stride, and build.py was rewriting ten bytes of bank 9
> data every build. Session 5 can translate the village prose without stepping on it.
>
> **The falsifier that found it is now the first line of §1** and it is the one to trust:
> banks 7, 8, 9, 10 and 12 must show ZERO rewritten bytes against `_base_expanded.gb`.
> Three separate false tables were corrupting game data at once and no other check saw any
> of them.

> **Session 3 landed 2026-08-04 and 15 names are awaiting Joey's ruling** — they are listed
> in `script/glossary.tsv`'s review page and marked there, not in the file. Nothing blocks
> session 4 meanwhile: a ruling changes a cell of `glossary.tsv` and `lint_en.py` then tells
> you every prose string that has to follow.
>
> ### THE ITEM LIST DRAWS A `[N]` AFTER STAFFS AND POTS, and it cost two names
>
> **Joey found this by playing, on 2026-08-04, after the whole battery was green.** He
> photographed `Stopgap Staff[6]`. The glossary had been sized against a bare name measured
> in a 17-cell row — measured honestly, but measured on an item that has no counter — so
> `Paralysis Staff` and `Pain Split Staff` were already losing characters on the real screen.
>
> `4:$5D58` writes `[`, calls the formatter at `4:$5CDC`, writes `]`. The formatter
> suppresses **at most two** leading zeros (`ld b,$02`), so the count is 1-3 digits and
> never padded: `[6]` is 3 cells, `[12]` is 4. Both routines charge `$C6DC`, the row's cell
> counter — the game measures this; it just has nothing to say when the total does not fit.
>
> **A staff or a pot may therefore be 13 cells, not 16.** Budgeted at two digits, because
> staff uses stack through fusion. `lint_en.py` now fails `counter_overflow`, and five names
> changed: Bind Staff, Sharing Staff, Gust Staff, Endless Pot, Hazel Staff.
>
> **The lesson is about the shape of the measurement, not the number.** `build/glossary_widest.png`
> was a real photograph of a real 16-cell name in the real box, and it was still the wrong
> measurement, because the sample had no counter. When you photograph a budget, photograph
> the WORST case, not a case.

---

## 0. What to read, and what not to

The repository now keeps only two active handoffs at its root. Completed implementation
records live in `docs/archive/`; reading them cold wastes a session unless you are changing
that subsystem.

| document | status | read it? |
|---|---|---|
| **`HANDOFF_NEXT.md`** (this) | live | **start here** |
| `TRANSLATING.md` | live | **yes, before touching `script/en.tsv`** — storage classes, cell budgets, control tokens |
| `HANDOFF.md` | live reference, ~1,500 lines | as a lookup, not front to back. `## Tools` and `## TRAPS` are the useful parts |
| `FINDINGS.md` | live reference | how the ROM works. Look things up in it; do not read it through |
| `docs/archive/README.md` | archive index | use it to find a completed subsystem record |
| `MESEN_SESSION.md` | superseded | routine regression is headless (`tools/gbrun.py`); Rankings R3 also has a completed manual Mesen acceptance record |

Memory (`~/.claude/projects/.../memory/MEMORY.md`) is the fastest orientation — one line per
fact, and it is current.

## 1. The standing verification battery

This project's culture is that a claim is measured, not argued. **Run these on every build
that changes bytes**, not just at the end:

```sh
sh build.sh                                     # Dot Gothic; must end "no problems" AND "every arena fits"
python3 tools/lint_en.py                        # control-token parity: 0 problems
python3 tools/dialogue_preview.py --check       # per-string geometry; exit 1 if any loses text
python3 tools/dialogue_preview.py --selftest    # the MODEL, against the Japanese. Both halves
python3 tools/crashscan.py build/shiren_en.gb --seeds 12
python3 tools/crashscan.py build/shiren_en.gb --seeds 12 --state saves/town.state
python3 tools/dotfont.py                        # approved source hash and glyph edits
python3 tools/fontaudit.py                      # proportional pixel budgets
python3 tools/logicdiff.py                      # banks 7,8,9,10,12 untouched; exit 1 if not
python3 tools/boxspill.py build/shiren_en.gb    # the box never draws another line's tiles
python3 tools/coverage.py                       # framed bytes, runtime starts + exact non-text classifications
python3 tools/menuspill.py build/shiren_en.gb   # includes exact Ground box-5 header path
python3 tools/groundspill.py build/shiren_en.gb # real Menu -> Ground route from supplied SRAM
python3 tools/rescuespill.py build/shiren_en.gb # real child-rescue stair route from supplied SRAM
python3 tools/koppastairspill.py build/shiren_en.gb # ordinary choice: Koppa x2 + Nagi + Fumi
python3 tools/koppatalkspill.py build/shiren_en.gb # shared phrase: town close + dungeon advance
python3 tools/copylogspill.py build/shiren_en.gb # direct + post-Quit Erase rebuild Copy Log in VWF
python3 tools/decoynamespill.py build/shiren_en.gb # real Decoy Staff battle-name route
```

> `coverage.py` is a static byte/alphabet census, not a runtime-entry census. The
> Nagi stair event entered eight bytes inside a record that coverage already counted,
> so its bytes were green while its independent start and translation were absent.
> `gbrun.py --dte-scan` now fails unexplained live starts; route fixtures such as
> `rescuespill.py` are what provide those starts. Both layers are required.

> **`tools/sealshot.py` is the same idea for the item screen's SEAL rows** (box `$13`,
> bank 4 dispatcher index 5), added in session 9. It supplies the seal ids at `$C6BE` that
> a save state has no reason to hold, which is what "forcing index 5 hangs" really was —
> `11:$7E40` was walking off its own table with a junk id and copying over live WRAM.
> `--all` walks all 20 in five screens; point it at `build/_base_expanded.gb` for the
> Japanese control.
>
> **`tools/msgshot.py` is not a check — it is how you LOOK at a screen you cannot reach.**
> It draws any bank-11/14 message on the real screen by substituting the queued pointer at
> `13:$67ED`, from `saves/sign.state`. Session A1's defect was invisible to every check
> above (the string round-tripped through the pool perfectly; it was the POINTER that was
> wrong) and the thing that had kept it open for three sessions was simply not being able
> to get a signboard on screen. Use it whenever a report names a screen a seeded walk does
> not reach.
>
> **`boxspill.py` is new in session 6 and it is the only check here that reads the SCREEN'S
> OWN memory rather than a model of it.** Every other line above compares the build against
> a model, and the column-19 spill was invisible to all of them because the model did not
> know the tilemap existed. It also only exists in frames the typewriter is mid-line, so a
> screenshot of a finished box does not show it either — this drives the game and looks at
> every frame. Run it on anything that touches the composer, the pen or the wrap width.

> **~~THE BATTERY HAS A HOLE IN IT AND IT IS THE BIGGEST ONE.~~ CLOSED 2026-08-05 by
> `coverage.py`.** Every other check here verifies that what we extracted round-trips,
> renders and fits. **Nothing checked that what we extracted is all there is** — so a bank
> could be 100% translated, green on every line of this file, and still speak Japanese on
> screen, which is exactly what happened after session 5 and what Joey reported an earlier
> session and was talked out of.
>
> **It is in `build.sh`, not just this list**, because its answer is an INPUT to other
> checks rather than a report alongside them: `dte_rom`'s code space is "bytes untranslated
> Japanese never uses", measured against `script.json`, so an incomplete `script.json`
> silently invalidated it for five sessions. A coverage number that is only correct on the
> days someone remembers to run it is not load-bearing enough for that.
>
> It CLASSIFIES rather than totals — the raw scan is ~22 KB and most of it is bank 10's
> item-stat table decoding as kana by coincidence. The gated number is dialogue: a run
> carrying `「` or a `<br>`/`<end>`/`<brk>`. Ten short runs in banks 1, 12, 27 and 29 are
> visible gibberish and are excused for sitting outside the script banks — they are printed
> in full on every run, never filtered away, so the exemption stays arguable.

> ### THE POOL VERIFIER WAS CHECKING THE WRONG THING, and it hid a real bug (2026-08-05)
>
> `build.py` verified a redirected string by taking `pool.record_offset` and reading
> forward to a terminator — which quietly asserted that a string's lines sit **contiguously**
> in the pool. The pool never promised that, and the runtime does not need it: `read_entry`
> resumes at `entry + 3`, the next **index** entry, wherever the text happens to be.
>
> It survived every earlier build because a build redirected two or three strings. Session 5
> redirected 355, and `14:$5875` became the first string to straddle two pool banks — lines
> 1-3 at the end of bank 34, line 4 in bank 35, line 5 back in a 17-byte gap in bank 34. It
> reported `BADPLACE`, which `TRANSLATING.md` tells a translator to stop and report as a tool
> bug. **It was one.** `pool.record_text` now walks the index the way the reader does.
>
> **And the corrected check immediately found a real defect underneath it.** `_add_entry`
> skips index addresses whose low byte is `$EE`/`$EF`/`$FF`, because a record's address is
> copied by a loop that stops on those. That rule applies to the **first** entry only — the
> one that travels inside a record. It was being applied to every entry, and the `$FF` filler
> it left between two lines of the *same* string is exactly what `entry + 3` walks into. Four
> of session 5's strings stopped part-way through on screen; `11:$5AE6` read back 145 bytes
> of 228. Fixed, with `pool.py --selftest` check 4b as the regression test — confirmed to
> fail on the old code, at iteration 42.
>
> **The lesson is the shape of the check, not the count.** A verifier that re-derives the
> value from the same assumption the writer used will agree with itself for ever. This one
> only started disagreeing when the data got big enough to break the assumption.

> **`logicdiff.py` IS THE ONE THAT FOUND REAL DAMAGE.** Every byte build.py rewrites outside a text arena is either
> a message-queue push (`ld bc,nn` reaching `0:$028B`, sometimes via a `jr` chain) or a
> declared patch (`tile_patches.tsv`'s BELLY strip at `2:$7D42`, name6, rank6, vwf,
> itemfix). Anything else is a pointer that was never a pointer. **Banks 7, 8, 9, 10 and 12
> must be ZERO** -- bank 10 is the numeric item stats and 25 bytes of it were being
> rewritten, bank 9 another 10, for three sessions without any check noticing, because it
> crashes nothing. This one line found more real damage than the rest of the battery
> combined; run it on every build that changes extraction.

> **`--selftest` was promoted into this list on 2026-08-04 and the reason is the lesson of
> session 4.** `--check` only measures the translation against the model; `--selftest`
> measures the MODEL against the shipped Japanese, and it is the only thing here that can
> tell you the budget itself is wrong. It was reporting a clean composer while the item
> descriptions were being measured 6 cells too wide and a line too shallow.

Add these when the change touches the composer or the font — VWF made them cheap and they
are the two that would catch it silently breaking:

```sh
python3 tools/vwf.py --selftest
python3 tools/build.py build/_base_expanded.gb script/en.tsv build/novwf.gb --no-vwf
python3 tools/msgdur.py build/shiren_en.gb   # and build/novwf.gb -- the numbers must match
python3 tools/gbrun.py build/shiren_en.gb --compare build/novwf.gb \
        --state saves/town.state --frames 400 --press b:120     # must be IDENTICAL
```

> **A pixel comparison against an older build now needs a cart both can read.** TWO save
> formats changed on 2026-08-03: the slot record grew from 79 bytes to 81 (§3 session 1) and
> the rank table's record from 10 to 12 (session 1b). An old `.srm` therefore renders
> differently in both places — not a regression. Compare on a blank `<rom>.ram`, against a
> `--no-name6` build (which implies `--no-rank6`), or from `saves/town.state`.
>
> **Both save states were remade on 2026-08-03 and are current** — `$D0FD` reads `Shiren`
> in each, and their SRAM is the 81-byte slot record and the 12-byte rank record. The
> pre-name6 originals are kept as `saves/town_prename6.state` and
> `saves/dungeon_stale_20260730.state`; those are `--no-name6` controls, not fixtures.
> **The remade dungeon state reaches real combat**, so anything that quoted a number from
> the old one (`msgdur` said 15 boxes; it now says 17) needs re-baselining once.

> ### THE BATTERY DOES NOT PLAY THE GAME. Joey has now found four defects that it missed.
>
> The name-entry box index and the cursor column (session 1b), the item list's `[N]` counter
> (session 3), and the column-19 spill (session 5, fixed in 6). All were green on every check
> in this file, because every check compares the build against a MODEL of the screen, and the
> model was the thing that was wrong. A screenshot only helps if it is a screenshot of the
> worst case: `build/glossary_widest.png` is a real 16-cell name in the real box, and it
> still missed the counter, because the item it photographed does not have one.
>
> **The spill adds a fourth way to photograph the wrong thing: at the wrong TIME.** It only
> exists while the typewriter is mid-line, so every finished-box screenshot in `build/` is
> clean and the bug was in all of them. `boxspill.py` closes that particular hole by looking
> at every frame, and it is the pattern to copy — **check the invariant, in the emulator's
> memory, on every frame** — rather than adding another model.
>
> **So: hand Joey a build after anything that changes what a player reads**, and say which
> screen to go and look at. That is the cheapest detector this project has, and the only one
> that has ever found these.

Add these when the change touches the ROM's structure rather than its text:

```sh
python3 tools/pool.py --selftest
python3 tools/reloc_verify.py build/shiren_en.gb build/base.gb --verbose
python3 tools/build.py build/_base_expanded.gb script/en.tsv /tmp/all.gb --redirect-all
python3 tools/build.py build/_base_expanded.gb script/en.tsv /tmp/shuf.gb --shuffle
```

**`--shuffle` + crashscan is not optional if you change a bank's layout.** It is the
falsifier for the invented-reference class that has now cost this project three sessions —
`0:$22BD` and `6:$472F`. If moving text breaks a bank, **suspect the reference list before
you suspect the bank.**

> `build.sh` deletes `build/_e.gb`. Keep a copy as `build/_base_expanded.gb` (setmapper →
> expand) or the `--redirect-all` / `--shuffle` builds have no input.

## 2. Where the script stands — current through 2026-08-11

> **2026-08-10 current count:** the table includes the three runtime-interior entries and the
> five completed visible name-grid rows: **1,404 supplied translations / 1,422
> extracted records**. The three added records are live interior starts `14:$5AFD`,
> `14:$5B81` and `14:$70BE`; they overlap bytes already counted in their parent records. The ten former
> script-bank embedded/unframed candidates are now structurally classified non-text, but
> 1,422 remains a manifest count rather than proof that every possible event text entry
> has been found.

```
bank    translated   total     what it is
  3          0 /    1      not text
  4          1 /    1      the Gld label
 11        643 /  643      DONE END TO END -- session 9 closed the 20 equipment seals
 13        352 /  359      DONE -- the 7 left are extraction false positives, not text
 14        337 /  338      DONE -- the 1 left is 14:$7EE6, 294 cells of decoded garbage
 30         18 /   21      DONE -- the 3 left are EMPTY: a bare $FF each. See session 9
 31         53 /   59      DONE -- the 6 left belong to the aliased, unrendered page 2
TOTAL     1404 / 1422      18 left: 6 aliased page records, 12 that are not text
```

> **~~The script is finished.~~ RETRACTED 2026-08-06, hours after it was written.** The
> table above is complete *about `script.json`*, and the opening cinematic has never been
> in `script.json`. **The denominator is not a total** — sessions 7 and 8b already taught
> that once, `coverage.py` was written so it would not have to be taught again, and the
> cinematic slipped past it anyway because `coverage.py` inherits `codec.py`'s character
> table and the cinematic does not use it. Read `1419` as "strings the extractor's
> character table can see", which is what it has always meant.

Every remaining entry in the table is either part of the aliased, unrendered second name
page or something no renderer draws. The visible grid remains fixed-cell but is fully
English. The separate cinematic TSV is complete;
V5D is now complete alongside V5A's approved full-screen copyright-card mock-up, V5B's
illustrated title and V5C's dungeon/town markers. All 22 native ending-credit cards remain
present and translated; the final Japanese end mark is intentionally preserved.
The active-dungeon Continue bubble is also English. Historical Session 10 below remains
the research brief for the remaining phase. Full-game playtesting can still expose unknown
runtime text or graphics, so this is a known-work statement rather than a claim that every
event route has been seen.

**Re-measure it with this, rather than trusting the table** — the numbers come from TWO
files and counting only `en.tsv` reports bank 11 at 233:

```sh
python3 - <<'PY'
import json, collections
strs = json.load(open('script/script.json'))['strings']
tl = {p[0] for f in ('script/en.tsv', 'script/glossary.tsv')
      for p in (l.rstrip('\n').split('\t') for l in open(f, encoding='utf-8'))
      if not p[0].startswith('#') and len(p) >= 2 and p[1].strip()}
tot, done = collections.Counter(), collections.Counter()
for s in strs:
    tot[s['bank']] += 1
    done[s['bank']] += s['loc'] in tl
for b in sorted(tot):
    print('%4d %6d /%5d' % (b, done[b], tot[b]))
print('TOT  %6d /%5d' % (sum(done.values()), sum(tot.values())))
PY
```

**Every string a player READS is now English**, on the evidence available: 11 of the 23 left
are the kana grid the name-entry picker still needs, and the other 12 are extraction false
positives or empty slots that nothing draws. `dialogue_preview --selftest` names `14:$7EE6`
as one of them and says why.

> **"TRANSLATED" IS NOT "RENDERS IN ENGLISH", and session A1 is what proves it.** All 25 of
> its strings were in this table's translated column, byte-perfect in the pool and green on
> every check in §1, while a player saw one Japanese glyph. This table is a statement about
> what is STORED. The only instrument that speaks to what is DRAWN is a photograph — from a
> save state, from a seeded walk, or from `tools/msgshot.py` for a screen neither reaches.

> **`total` is MEASURED, and as of sessions 7 and 8b it is complete as far as anything can
> currently tell.** It used to be whatever `script.json` happened to hold. `tools/coverage.py`
> reports zero unextracted dialogue in the script banks in BOTH classes it knows how to
> look for: `$FF`-framed runs, and text stretches embedded in runs that also hold non-script
> bytes. Its 10 script-bank heuristic hits are explicitly tied to non-text consumers and
> exact-byte guarded; none is prose.
>
> **That is "no evidence of more", not "there is no more".** The two gaps this project has
> found were both invisible to the check that existed at the time. What is different now is
> that the number is printed on every build and a regression fails it.
>
> **The translated column did not move, and that is the regression test passing.** It read
> 592/352/204/18/45 before re-extraction and reads 592/352/204/18/45 after; only the
> denominators grew. The old table's `14: 207/207` was never right — it was 204/207 when
> written, and "DONE" was measured against a denominator missing 117 strings.

`script.tsv` is 1404 now. It went 1263 → 1261 → 1404: the glossary session recovered three
names a linear scan had read as an opcode, session 4 dropped `13:$57AB`, `11:$5848` and one
more that were never strings at all, and session 7 added 143 that were always there. **A
count going DOWN was the healthy direction while the rule was getting stricter; it going UP
by 143 was the rule getting CORRECT.** Neither number was ever a total until `coverage.py`
existed to say so.

**Space is still not a constraint.** Every arena projects positive at the endgame ratio AND
at the ratio-independent floor — bank 13 finished the session at `+3928` projected with
324 strings in it. See `TRANSLATING.md` §3. Display constraints are now tracked as pixels,
source staging, temporary tiles and runtime variants in `VWF_BUDGETS.md`; control-token
parity remains independent.

## 3. The sessions

### ~~Session 0 — close the space problem~~ — **DONE 2026-08-03**

> **Start at session 3, the glossary.** Sessions 1, 1b and 2 all landed on 2026-08-03:
> the player name is six characters, the rankings board stores and draws six, and the
> composer draws 24 characters a line. ~~**The caps in §4 are settled.**~~ **Retracted
> 2026-08-09:** that was a uniform-font source contract, not a Dot Gothic pixel
> measurement. The glossary remains frozen for terminology; its old 14/16 guards are
> reopened in session 3e and `VWF_BUDGETS.md`.
>
> The formerly open name-entry grid re-layout was completed as Session 3b on 2026-08-10.

### ~~Session 1 — player name 4 → 6 characters~~ — **DONE 2026-08-03**

`tools/name6.py`, applied by `build.py` (bisect control: `--no-name6`). Name entry and
Rename both accept six characters, the name survives save → reload, and the log list draws
it. `dialogue_preview.PLAYER_NAME` is 6 and `--check` is clean at it — no translated line
lost headroom, because no translated string uses the `<name>` (`$EA`) token yet.

**Evidence:** `build/name6_field.png` (the entry box), `build/name6_newgame_reload.png`
(`1:bCmBY Shiren / Moonlight / 1回目`, against the control's `Shir`), and

```sh
python3 tools/namerun.py <rom> --fresh --ram <blank> --name Shiren --end --sram --reload
python3 tools/namerun.py <rom> --rename --ram <save> --name Keyaki --end --sram
```

Battery green: 1499 checks, 12/12 crash seeds, `--shuffle` and `--redirect-all` clean,
`gridprobe` 0 wrong on every row and the page-2 alias, status screen and file menu
pixel-IDENTICAL against `--no-name6`, `msgdur` 12 boxes to 12.

> **THE SAVE FORMAT CHANGED.** The record is 81 bytes, not 79. A save written by an older
> build still loads and does not crash, but every field past the name is read two bytes
> early — the log list drops its place name. Joey's `saves/shiren_en.srm` is in the old
> format; make a new log, or build with `--no-name6` to read it.

#### The rankings board still shows 4 of 6 — **handed off as session 1b, below**

**Joey, 2026-08-03: `Shiren` → `Shirn`, `Poopin` → `Poopn`, `Abcdef` → `Abcdn`.** Everywhere
else is correct. This is the second record the old brief parked, and it predicted exactly
this: *"the 10-byte `$D60F` payload — `15:$52DB`, which also copies 4 name bytes — stays at
four characters until someone establishes what reads it. Flag it if a name shows up
truncated somewhere unexpected."* The rankings are what reads it.

**`Abcdef` → `Abcdn` is the measurement that settles it.** The fifth glyph is not the name's
last character — it is the same `n` every time, so the rank row is drawing **the four stored
name bytes plus the byte after them**. The name run stops at `$FF` and a 4-character name
has no terminator inside a 4-byte field, so it runs on into the next field, which holds 50
(`$32`, which the Latin font draws as `n`) — the same 50 the row prints as a number. A
3-character Japanese name is `4D 6B 6F FF` and terminates, which is why `シレン` renders
correctly in the same list and why the original game never showed this.

**The payload is full — all ten bytes are live**, which is what makes it a sitting rather
than a byte:

| payload | address | written by | holds |
|---|---|---|---|
| 0-3 | `$D60F-$D612` | `15:$52DB`, `ld e,$04` | the name |
| 4-6 | `$D613-$D615` | `5:$4766` (3 bytes from `$FF90`) | score / floor / level |
| 7 | `$D616` | `15:$52D8` | flags |
| 8 | `$D617` | `15:$52F3` | `$C9DD` |
| 9 | `$D618` | `15:$52FA` | `$C9DE \| c` |

**This is a RECORD LAYOUT problem, not a space problem and not a cell problem.** The ROM has
~484 KiB free and that is irrelevant; so is VWF, which changes pixel widths on the composer's
dialogue path while the rank row is a fixed-width tilemap screen. (An earlier draft said
"not worth doing before VWF" — an ordering remark that read as causation. Joey caught it.)

**Fixed in session 1b below** — though not the way this paragraph expected. The payload map
above is correct and the diagnosis held up exactly. What changed the answer was a guess
nobody had questioned: the *renderer* was already drawing six cells, so the whole job was
storage, and approach 1 (grow the record) turned out cheaper than rehoming.

**TWO bugs got past the whole battery, and Joey found both by playing.** The field's width
lives in THREE places and the patch first moved only one of them:

| what | where | symptom |
|---|---|---|
| the width nibble | `4:$5E91 ld a,$40` | — (this one was patched) |
| **the box index** | `4:$4B10 ld a,$0A` | held six, DREW four: `Shiren` clipped to `Shir` |
| **the cursor's column** | `4:$5EE8`, the `$C6F7` bit-1 branch | underline under the SECOND character |

`4:$4B02` builds the name screen as `call $5E6E` (which sets the width) plus a hardcoded
box 10 — 4 cells — while its twin `4:$4B20` is the same screen at six (`call $5E9A` + box
11). And `4:$5EDD` draws the underline at `$C347 + cursor` or a flat `$C348` depending on
bit 1 of `$C6F7`, which is not a cursor flag: it is *which of the two screens is up*, and
those two bases are the two boxes' first text cells (box 11 is at x=6, box 10 at x=7).

Both are one byte. `4:$4B10` → `$0B`; `4:$5EE8` `jr nz,` → `jr `, making the branch
unconditional so the two callers cannot drift apart again. Both symptoms healed themselves
on the first keypress, because `4:$6150` — the cursor REDRAW — does derive the box and the
column from the width. Only the initial draw was wrong, which is exactly why a screenshot
taken after typing looked fine.

**Third and fourth instances of a renderer's geometry duplicated where no reference can
follow it** — after the picker stride (`31:$41A0`) and the death-message address
(`13:$405F`). 1499 checks, 12 crash seeds, `gridprobe` and two pixel comparisons were all
green, on the wrong picture. **Photograph the screen you changed, in its INITIAL state, and
look at it.** I had the screenshot and read past it.

(The odd backspace behaviour Joey saw alongside these — Bck clears from the cursor to the
end, and backspacing past the first character reloads the default name — is the ORIGINAL
game's. The `--no-name6` control does exactly the same, at four characters.)

**Two things the brief below got wrong, both caught by measurement rather than review:**

1. **The record had to grow FORWARD, not backward.** Prepending to `$A6FE` was the design;
   `$A680..$A6FF` is a live 128-byte block mirrored to SRAM bank 0 `$A806` and re-cleared to
   `$FF` right after the template is written, so the record came back with `$FF` in its first
   two bytes and the log list read `65535回目` for `1回目`. The `51 A4 EE DB` at `$A74F` that
   made appending look unsafe is **uninitialised cartridge SRAM** — a fresh save written by
   the unpatched build has `$FF` there. Deciding this from a real `.srm` was the error;
   deciding it from a save the ROM wrote was the fix.
2. **`15:$7F27` and `4:$7F21` are not free space.** They are runs of `$00` inside the sparse
   tail blob each bank ends with. Nothing in the ROM names them and nothing proves they are
   dead, and zeros in a bit table are data. What paid for the eight bytes bank 15 needed is
   in `tools/name6.py`'s docstring: the 81-byte new-game template moved to bank 32 behind a
   `rst $10` far call, which also left **80 spare bytes at `15:$5A31`**.

   Smaller errors, all caught by the opcode assertion before each write: three `cp $4F`
   addresses were off by one or four, two summary offsets were wrong (52→**56** not 54,
   86→**92** not 90), and three more `ld hl,sp+n` sites (7, 41, 75) were missing entirely.
   **Do not hand-transcribe an operand list.** `name6.py` decodes forward and derives them.

The original brief is kept below because its research is what made the session possible.

<details><summary>The 2026-08-03 brief, as written before it was executed</summary>

**Do this before any prose.** It settles one half of the `<var>` budget every combat line is
written against; doing it after the prose means rewriting the prose.

**The old brief here was wrong and has been replaced.** It said "the caps are two `ld d,$04`
bytes, one-byte patches each", from memory `shiren-gb-name-length`. That memory also said
"the field looks 8 bytes wide — **verify before relying on it**". It was verified on
2026-08-03 and **it is not**. Reproduce the bug in one command:

```sh
python3 tools/namerun.py build/shiren_en.gb --name Shiren     # types "Shin"
```

#### What was proved to work (measured, on screen)

The 4-character limit is **one nibble**, not the `ld d,$04` pair. `$C6E2` packs
`width << 4 | cursor`, and `4:$5E91 ld a,$40` is what sets width 4. Patch that byte to `$60`
plus the two pack/unpack caps and the field accepts six characters — **and the ROM already
has a wider box for it**: `4:$6150` picks the box from the width (`$0A` at `$C348` for
width 4, `$0B` at `$C347` otherwise), and `4:$5E9A` already sets width 6 for another screen.
Photographed: "ABCDEZ" and "Shiren" drawn correctly in a box one cell wider each side.

The prototype is kept as **`build/name6_proto.gb`** (gitignored, regenerable): it is
`shiren_en.gb` with exactly three bytes changed — `4:$5E92` `$40`→`$60`, `4:$7623` and
`4:$7648` `$04`→`$06` — with `build/name6_proto.png` / `_field.png` as the evidence. It
types and draws six characters and **still saves four**, which is precisely why the rest of
this section exists.

#### Why it is not landed

**A 6-character name that saves as 4 is worse than no change**, and the name is threaded
through four structures that are each sized *exactly* 4, or exactly full:

| structure | width | why it cannot just grow |
|---|---|---|
| packed buffer `$D100` | 4 | `$D104` starts a live 120-byte block (→ SRAM `$A6DC`, bank 3) |
| SRAM slot record `$A700` | 79 entries | scatter/gather; see below |
| file-select summary | 34 B | status byte + the record's first 33 bytes, stride `$22` |
| the 107-byte summary buffer | 3×34 + 5 | `15:$4F90`'s scratch sits at `+102`, right behind them |

(`4:$6D43`'s 12-byte message payload carries the name too, but it has room — see the
`15:$5183` note at the end of this section. The 10-byte `$D60F` record also holds a name and
is full, but it is **not** on the name-entry path; it is not a blocker.)

**The save record is a scatter/gather list**, which is the key discovery. `15:$59E3` holds
**one 16-bit WRAM/SRAM pointer per record byte**; `15:$4F49` gathers them into SRAM and
`15:$597E` scatters one back. `15:$592F` classes each byte 0/1/2 and `15:$5994` is the
79-byte new-game template — whose offset 2 holds `4D 6B 6F FF`, the default name シレン.

So the name's SRAM home is **entries 2-5 of a pointer table**, and it needs 6. Measured:
all 79 pointers are distinct, entries 6-8 (`$D3FC`-`$D3FE`) are referenced from ~150 sites
in bank 28, and `$D71F`/`$D723`/`$D724` are referenced from bank 15 — **there is no spare
entry to steal.** Joey chose to grow the record rather than take bytes from live state.

#### The design that came out of it — execute this, do not re-derive it

**Grow the record 79 → 81 and move its base back 2, to `$A6FE`.** Prepending is what keeps
every existing field at its current SRAM address; appending would land on `$A74F`, which
holds real data (identical in all four slots). The 128 bytes before each of the four slot
bases (`$A700`, `$AE80`, `$B600`, `$BD80`, stride `$780`) are `$FF` in a real save and are
explicitly cleared to `$FF` by `15:$4E67`, so the two new bytes are free.

Record layout: `[0]=old[0] [1]=old[1] [2..7]=name[0..5] [8..80]=old[6..78]`. Old entries
6-78 keep their exact SRAM addresses, so `$A723` and `$A727` (written directly by
`15:$51E2`/`15:$51F8`) need no change.

* **Bank 15 tables** repack into the 338 bytes at `$592F..$5A80`: class 81 B at `$592F`,
  template 81 B at `$5980`, pointers 162 B at `$59D1`, 14 B spare. That works only because
  the 22-byte helper at `15:$597E` moves to the **17 free bytes at `15:$7F27`** — rewrite it
  to drop `push af`/`pop af` (callers reload `a`) and replace `sla e` with two `add hl,de`
  (`d` is 0 at all three call sites), which is exactly 17 bytes. `rst $20` preserves `de`
  (`0:$0868`), so that is safe.
* **Consumers to repoint:** base `$A700`→`$A6FE` at `15:$4E11 $4F4D $58B7 $58D9 $58FD`;
  `$AE80`→`$AE7E` at `15:$4F96`; `ld e,$4F`→`$51` at `$4E14` and `cp $4F`→`$51` at
  `$58CC $58EF $5916`; `cp $9E`→`$A2` at `$4F64`; `ld hl,$5994`→`$5980`; `ld hl,$59E3`→`$59D1`
  at `$4F53` and in the moved helper; `call $597E`→`call $7F27` at `$58C6 $58EA $590E`.
* **The summary cascade — this is the part that makes it a session, not an hour.** Inserting
  2 bytes shifts every record field at old offset ≥6 by +2, so the summary must copy 35 not
  33 (`15:$5011 ld e,$21`→`$23`) and its stride 34→36 (`15:$4FBE`). That moves
  `15:$4F90`'s scratch, so **ten** struct offsets change: `$0066`→`$006C` (`$4F99 $4FCB
  $5006`), `$0068`→`$006E` (`$4FAB $4FDD $4FF7`), `$0069`→`$006F` (`$4FA4 $4FB9 $4FED`).
  Then `4:$6671 add sp,-107`→`-113`, and **twelve** of the 22 `ld hl,sp+n` operands in
  `4:$666D` shift: 30→32, 32→34, 33→35, 34→36, 35→37, 37→39, 64→68, 66→70, 67→71, 68→72,
  69→73, 71→75, 98→104, 100→106, 101→107, 18→20, 52→54, 86→90. The name stays at sp+3.
* **Bank 4, the cheap half:** `4:$5E91 ld a,$40`→`$60`; caps `$04`→`$06` at `4:$7622`
  `4:$7647` `4:$675D` `4:$6D8F`; and rehome the packed buffer `$D100`→**`$D0FD`** (6 bytes,
  terminator slot `$D103`, inside the 187-byte untouched run `$D045-$D0FF`, no ROM reference)
  at `4:$675A $6D8C $6EA5 $761C $7637` and `15:$52DE`.
* **Default name** (Joey asked for this in the same session): the two 4-byte literals
  `4:$6EC4` and `4:$6B89` have no room for `Shiren`+`$FF`; put one shared 7-byte literal in
  the 52-byte hole at `4:$7F21` and repoint `4:$6EA8` and `4:$6B7B`. Template offset 2
  becomes the same six bytes.

**`15:$5183` is not a problem, and it is not Rename — traced, do not re-litigate.** It writes
the name to SRAM (`ld bc,$A702` / `ld e,$04`) and it is **the normal New Log save path**:
confirming a name fires `4:$7618` → `15:$5183` → `15:$519E`. It is reached as **message type
7** through the jump table at `15:$5043`, which is the `ld a,$07 / call $6D43` that `4:$6093`
sends. Its source is `de+2` where `de` is `4:$6D43`'s **12-byte stack payload**, not the
10-byte `$D60F` record — the name sits at `sp+2..sp+5` and `sp+2..sp+7` is free, because the
only other command writing that high is `$0B` at `sp+8..sp+11` and no two commands run at
once. So it is two more immediates: `15:$519E`→`ld bc,$A700` (the name's new base) and
`15:$51A7 ld e,$04`→`$06`, matching `4:$6D8F ld b,$04`→`$06`.

*(The 10-byte `$D60F` payload — `15:$52DB`, which also copies 4 name bytes — did **not** fire
on name confirm. It is some other record, probably death/rescue, and it stays at four
characters until someone establishes what reads it. Not a blocker; flag it if a name shows
up truncated somewhere unexpected.)*

**Then** set `dialogue_preview.PLAYER_NAME = 6` and re-run `--check`: lines that fitted a
4-character name may not fit a 6-character one. That is the point of doing it now.

**Exit:** name entry accepts 6 characters, the name survives save→reload and shows six
characters on file select, `tools/gridprobe.py` clean, the battery in §1 green with
`PLAYER_NAME = 6`.

</details>

### ~~Session 1b — the rankings board shows 4 of 6 characters~~ — **DONE 2026-08-03**

`tools/rank6.py`, applied by `build.py` (bisect control: `--no-rank6`, implied by
`--no-name6`). **Approach 1, not approach 2** — Joey chose it once the measurements were in,
because they inverted the two options' costs. See "What the measurements changed" below.

**Confirmed working by Joey on a real cartridge run, 2026-08-03**, after the two-bug fix
recorded further down. Six characters on the board, and the ranking result screen is back.

**Evidence:** `build/rank6_before.png` (`Shirn` / `Poopn` / `Abcdn`) against
`build/rank6_after.png` (`Shiren` / `Poopin` / `Abcdef`), same save, same page.

#### The symptom, measured

`Shiren` → `Shirn`, `Poopin` → `Poopn`, `Abcdef` → `Abcdn`. **The fifth glyph is the same
`n` every time** — that third sample is what settles it, and it is why this is not "shows 5
of 6". The board draws the four stored name bytes and then runs one byte too far.

#### Why, established

The name run stops at `$FF`. The stored field is exactly 4 bytes, so a 4-character name
carries no terminator and the run continues into the next field, which holds 50 — `$32`,
which the Latin font draws as `n`. It is the same 50 the row prints as a number a few cells
left. `シレン` is `4D 6B 6F FF` and terminates, which is why it renders correctly in the same
list and why the original game never showed this: Japanese names were short enough to keep
their terminator.

#### The record, measured — all ten bytes are live

`15:$52DB` builds a 10-byte payload at `$D60F`:

| payload | address | written by | holds |
|---|---|---|---|
| 0-3 | `$D60F-$D612` | `15:$52DB`, `ld e,$04`, source `$D0FD` | the name |
| 4-6 | `$D613-$D615` | `5:$4766`, three bytes from `$FF90` | score / floor / level |
| 7 | `$D616` | `15:$52D8` | flags |
| 8 | `$D617` | `15:$52F3` | `$C9DD` |
| 9 | `$D618` | `15:$52FA` | `$C9DE \| c` |

`15:$5382` copies a type byte plus those ten into a struct **built on the stack** at
`15:$533C` (`add sp,-47`) — transient, not the stored table. `15:$53C5` then builds a display
descriptor over it and treats payload byte 4 as the next field's start (it stores a pointer
to `de+5` at `de+$0B`), which independently confirms the name field is four bytes with a
live neighbour.

#### The two approaches

1. **Grow the record** — payload 10 → 12, `15:$5382`'s `ld e,$0A` → `$0C`, and the rank
   table's stride and storage behind it. This is what the save record needed in session 1.
2. **Rehome the names** — leave the 10-byte record alone and put a parallel array of 6-byte
   names somewhere with room, indexed by rank slot. **This is what Joey wants.** It is the
   SNES Shiren repo's fix for the same class of bug, and it is what `$D100` → `$D0FD` did for
   the WRAM buffer in session 1: when a field cannot grow in place, move it somewhere that
   can. It also leaves every existing byte of the record where it is, so the blast radius is
   the name's readers and writers rather than the whole table.

#### What was established, and what it changed

Both of the old brief's "NOT established" items are now measured, and the second one is the
finding that reframed the whole session.

* **Where the table lives.** SRAM **bank 3**: a 496-byte master block at `$BE00`, copied to a
  working copy at `$A000` (`15:$5553`/`$5575`) and staged into WRAM `$D61B`. It is 16-byte
  header, **table 1 (20 x 10)**, a 32-byte gap, **table 2 (20 x 10)**, then a 48-byte tail
  whose `$A1E0` is live. The old note "in a real `.srm`, bank 3 `$A000` is dungeon data" was
  right and misleading: `$A000` is the *working* copy and is `$FF` at rest — the master is at
  `$BE00`. Record: `name[0-3]`, `score[4-6]` 24-bit LE, `floor[7]` (low 6 bits, drawn +1),
  `count[8-9]` 16-bit LE.
* **THE RENDERER WAS ALREADY 6 CELLS WIDE.** `31:$46BC` -> `31:$4A4B` far-calls bank 4
  (`rst $08 / db $29,$04`), which copies **six** bytes into a scratch buffer at `$C6E3` and
  appends `$FF`; `31:$4A5F` draws until `$FF` with no cap. Proved by crafting a record of ten
  distinct letters: it drew exactly `ABCDEF` and byte 6 appeared in the score column. So the
  brief's fear — "if it draws a fixed 5 cells, neither approach shows six" — was the opposite
  of true, and **no renderer change was needed at all.**

**Why approach 1 won.** The measurements inverted the costs the brief assumed. Approach 2 got
*harder*: free space inside the persisted block is ~78 bytes against the 240 a full parallel
array needs, and a parallel array has to be shifted in lockstep with the records at a
different stride. Approach 1 got *easier*: the 32-byte gap sits directly after table 1, so a
12-byte record fits **19** entries in the space 20 ten-byte ones used, and the insert keeps
its **single** record-moving primitive (`15:$5492` -> `15:$54B3`). Joey took approach 1 with
the trade-off stated: one rank slot per board.

New record: `name[0-5] score[6-8] floor[9] count[10-11]`, stride 12, 19 entries.
Table 1 `$A010..$A0F3`, table 2 `$A0F8..$A1DB`, WRAM staging `$D61B..$D6FE`.

#### Three things worth not re-deriving

1. **The staging grows past `$D6E2` into shared scratch, and that is safe — measured, not
   argued.** Banks 2, 5, 16, 19 and 26 all name addresses inside the existing 200-byte
   buffer, so no static scan can settle it. Stamping `$D6E3-$D6FF` with a pattern once the
   board is up and driving it for 1,920 frames overwrote **not one byte**. The staging is
   also re-loaded from SRAM on every visit (`$54C4`) and written back (`$54EA`), so it never
   has to persist — the only requirement is that nothing writes it while the board is up.
2. **The 10-byte payload at `$D60F` cannot grow**, so the name is not sourced from it:
   `$D619` is a live flag and `$D61B` is the staging base right behind it. The struct builder
   `15:$5382` was replaced (45 bytes, in the 80 name6 left free at `15:$5A31`) with one that
   assembles the record from **two** sources — six name bytes from `$D0FD` and six from
   `$D613`. `15:$52DB`'s 4-byte copy into `$D60F` is deliberately left alone, because
   `15:$4082`/`$4096`/`$409F`/`$40AD` still read that payload.
3. **Sweep for the field offsets; do not follow the calls.** The first draft patched the five
   offsets it had read the code for and the board drew the count as **1024 for 1** — three
   more readers (`31:$47AA`, `$47FE`, `$4833`) were only found by sweeping the whole drawer
   block for `ld de,$00nn`. `rank6.install` now does that sweep at build time and **fails**
   on an unclassified immediate. Two operands must NOT move and `--selftest` says so:
   `15:$5438`'s `$0002` and `15:$5473`'s `$0004` (count-minus-score is 4 in both layouts).

#### TWO BUGS SHIPPED IN THE FIRST BUILD, and Joey found both by playing

Same failure as session 1's: **the whole battery was green on a patch with two sites
missing.** Both were omissions from the patch tables — I had derived both while designing and
then never added them — and neither is visible to anything that does not actually die.

| site | should be | symptom |
|---|---|---|
| `15:$54B7 ld e,$0A` | `$0C` | the record copy still moved **10 bytes of 12**, dropping the count |
| `15:$535E ld hl,sp+18` | `sp+20` | the rank index moved `+$12`→`+$14`; this reader did not |

**The count is not just a display field — it is the occupancy marker.** `31:$46B1` reads
record+10/+11 to decide a slot is empty, and the insert's own empty test (`15:$5473` +
`$547E`) reads the same field. So every entry was written correctly, then treated as absent:
the board drew **nothing**, and because every slot looked empty the insert forced its
"insert here" result and stopped sorting by score. `15:$535E` fed a pointer's low byte to the
far call that shows the result screen on death, so **no result screen appeared**.

**The guard now covers bank 15 too, and it is verified to fire.** `rank6.install` sweeps
`15:$53C5-$54C4` (all small immediates *and* `ld e,$nn`) and `15:$533C-$5382` (`ld hl,sp+n`),
and every operand must be either patched or named in `KEEP_STRUCT`/`KEEP_STACK` with the
reason it is safe. Dropping `$54B7` from the tables now fails the build naming that address.
I had written exactly this lesson for bank 31 in the same session and then failed to apply it
to bank 15 — **sweep every range the stride touches, not just the one that bit you.**

Verified after the fix: the count survives the copy (`03` preserved end to end), the rank
index reads `0` for first place instead of `$21`, placement is score-driven again (a score-0
record lands behind eight higher entries), and the death sequence is **pixel-identical to a
`--no-rank6` control** through 500 frames but for a 2x2 cursor-phase pixel.

> **A save written by the broken build has damaged entries** — their counts are gone, and the
> board stops at the first zero-count slot. `python3 tools/rank6.py --repair old.srm new.srm`
> sets a count of 1 on any record that has a name but no count. The true count is not
> recoverable, and entries inserted while the bug was live are in the order they were written
> rather than by score; new entries sort correctly.

#### THE RANK SAVE FORMAT CHANGED — and there is a converter

A board written by an older build is read at the wrong stride. Measured on Joey's save: it
draws garbage rows, **does not crash**, pages normally and exits cleanly. There is no version
marker in the block, so nothing can auto-detect it.

```sh
python3 tools/rank6.py --upgrade saves/shiren_en.srm saves/shiren_en_new.srm
```

Converts both tables, refuses to overwrite an existing file, and leaves the input untouched.
Run it **exactly once**. Joey's 8 entries carry over with scores, floors and counts intact;
the names keep their four stored characters and gain a terminator, so they read `Shir` rather
than `Shirn` — characters 5 and 6 were never stored and cannot be recovered. A 20th entry, if
any, is dropped.

> **`saves/dungeon.state` and `saves/town.state` predate name6** (2026-07-30). Their WRAM
> still has the packed name at `$D100`, so anything reading `$D0FD` sees `00 00 00 Shi`. That
> cost an hour here: the insert path looked broken and was not. They are fine for everything
> that ignores the name, but **remake them before testing anything name-shaped** — boot,
> `start` x4, `a`, `down` x2, `a`, `a`, ~4,600 frames.

**Exit, met:** six characters on the board (`build/rank6_after.png`); §1 battery green —
`build.sh` no problems / every arena fits, `lint_en` 0, `dialogue_preview --check` 0,
**crashscan 12/12**, `pool --selftest` 8, `reloc_verify` 0 mismatches, `--redirect-all` and
`--shuffle` clean, `rank6 --selftest` all pass; `namerun` still round-trips both entry paths
(`Shiren` and `Keyaki` at `$A702`); and the file menu and status screen are **pixel-IDENTICAL**
against a `--no-rank6` control. The write path was verified on a real death: the builder
emits `Abcdef` in full and the sort shifts records at `$D6F3 -> $D6E7 -> ... -> $D67B`, all
12 apart, placing the new record in slot 8 behind 8 existing entries.

### ~~Session 1c — remake the save states~~ — **BOTH DONE 2026-08-03**

1. **`saves/town.state` is remade and current.** It is Moonlight village on Joey's newest
   save (`Shiren`, log 4, the 12-byte rank table), written by today's `build/shiren_en.gb`,
   and `$D0FD` reads `1d 2c 2d 36 29 32` — the name, where name6 put it. The 2026-07-30
   originals are kept as **`saves/town_prename6.state`** and
   **`saves/dungeon_stale_20260730.state`**; they are `--no-name6` controls, not fixtures.
   Verified after the swap: `crashscan --state saves/town.state --seeds 4` clean, and
   `pool_verify` reaches the inn wake-up scene and reads English out of it.

   > **`saves/dungeon.state` is remade too, 2026-08-03, once Joey gave the route.** It had
   > to be WALKED into — **Shiren does not let you save inside a dungeon**, so no `.srm`
   > will ever hold a log parked on a floor and the old recipe ("`down` x2 to reach log 3")
   > describes a save that cannot exist. Four 20,000-frame seeded random walks never left
   > the village, so this was never going to be found by search.
   >
   > **The route, from `saves/town.state` (which starts inside the first house):**
   >
   > ```
   > down x40                      out of the house
   > left  x190, `a` every 4th     west across town, clearing the villagers' text, out
   >                               the west gate, one more square, accept -- dungeon 1F
   > ```
   >
   > **`tools/mkstate.py <rom> <srm>` does all of this and writes both states**, so the
   > next layout change is a one-command regeneration rather than an afternoon. Pass
   > `--png-dir` and LOOK at the two frames: a state that loads is not a state that is
   > where you think it is.
   >
   > That is ~1,150 frames at 6 frames a step. The 2026-07-30 file is kept as
   > `saves/dungeon_stale_20260730.state`. The remade one reads `Shiren` at `$D0FD` and is
   > a strictly better fixture: the seeded walk now reaches **real combat**, so `msgdur`
   > sees 17 message boxes where the old one saw 15, and `msglog` logs 140 composer lines.
   > **Re-baseline anything that quoted a number from the old state.**

2. ~~**Re-lay-out the name-entry grid.**~~ — **DONE in Session 3b, 2026-08-10.**
   Joey settled the open question on 2026-08-04: *"I would simply remove the other page
   behaviour and just clean up the grid alignment."* See below.

#### The name-entry grid — the analysis, kept because session 3b is written on it

```
row 0:  CAPS  Fwd Bck  End      <- header; these words are SELECTABLE
row 1:  ABCDE Zabcd  uvwxy
row 2:  FGHIJ efghi  z.,'?
row 3:  KLMNO j k l  01234
row 4:  PQRST mnopq  56789
row 5:  UVWXY rst??  +?[]?
```

It inherited the **kana** layout's shape with English poured in: uppercase runs A-Y down the
left block, **`Z` is orphaned** at the head of the lowercase block, and rows 3 and 5 have
gaps (`j k l`, `rst??`) because the Japanese rows there held only three kana each.

* **Rearranging within the existing grid costs nothing.** Same box, same 5 x 18 cells, same
  stride — it is a content edit of five strings. The picker reads
  `base + (row-1)*stride + column`, so whatever is displayed at a cell is what that cell
  selects; `build.py` derives the stride and asserts the rows are evenly spaced, and
  `tools/gridprobe.py` proves every row reads the byte it draws. 62 characters in 90 cells
  is not a tight fit.
* **Mind the blank cells.** A gap in `j k l` is a selectable cell that yields a space. Decide
  deliberately whether a space belongs in a name rather than closing the gaps by accident.

### Session 3e — item-name budgets after VWF — **REOPENED 2026-08-09; measure before linting**

> **The old 14-cell conclusion is not the final VWF budget.** It correctly described the
> original 17-cell *source stager* (`name + signed modifier`), but Joey's real-game
> photograph of `Accurate Sword+99` showed the proportional menu result advanced **90px**,
> painted 89px and needed 12 tiles inside the 128px name payload. The later approved
> compact-plus edit makes `+99` 88px/87px/11 tiles. Exhaustive suffix measurement after
> Joey's final four-column 4/7 found a 144-way peak tie; deterministic representative
> `Accurate Sword-99` is 88px/87px/11 tiles.
> Do not add the proposed
> 14-character lint: that would freeze a fixed-cell implementation limit into translation
> policy after the screen stopped being fixed-width.
> `fontbakeoff.py --approved-dot --digit-review` reproduces the installed source/approved
> 4/7 comparison. Joey then supplied the final four-column `4` and `7`; the latter keeps
> its top-right corner, a three-step diagonal, and a straight lower leg.
>
> The first test helper forged `$C549`, which is only a six-byte display copy. It looked
> right but Equip/Drop followed the absent canonical object, producing Club behaviour and
> a pitfall graphic. `tools/mesen_spawn_accurate99.lua` now appends a genuine eight-byte
> object through SRAM-bank-0's `$A3B0` index list and `$A406` object table. PyBoy exercised
> the real action paths: Equip says `Took Accurate Sword+99`; Drop changes the object flags
> `$84 -> $80` and draws the weapon on the floor; stepping away and back says
> `Got Accurate Sword+99` and restores `$80 -> $84`.
>
> **Menu and dialogue are separate budgets.** With the tested suffix `-77`, the
> pickup is 107px/21 characters and renders whole; Equip is 113px/22 and renders whole.
> The Drop line is 135px advance / 134px painted / 26 characters. The old 24-character
> source contract dropped its suffix; the accepted 30-glyph/144px reset now renders it.
> The lesson survives: source staging and pixel width must both be measured.
>
> **A second screenshot exposed a position-dependent allocator assumption.** At the top
> of either five-row item page, the 12-tile name fell back to fixed width and its final
> `9` wrapped into row 1; moving the same object lower made it proportional. (This was
> before the compact-plus edit; the intermediate compact-4 shape preserved that 12-tile
> regression.) Row 0 had
> been forced into the 11-tile auxiliary run because the old hostile fixture used five
> 11-tile names. It now means only “reset the epoch”: the first item that *fits* 11 tiles
> takes that run, while a wider first row takes base. The current hostile fixture is exactly
> five 11-tile item rows plus four 4-tile verbs = 71/72 and passes plane-exact.
>
> **Historical experiment, superseded:** raising 24→26 in isolation was reverted because
> it changed automatic box boundaries before the full renderer audit existed. The completed
> audit intentionally adopts 30/144, reflows authored prose, and records the seeded result
> (11 boxes) as pacing-review input. The temporary `Left <item>` wording remains rejected.
>
> Remaining measurement: finish the `<var>/<cE3>` producer-to-template census beyond the
> already enumerated item suffix/count classes. Keep it as explicit runtime review; do not
> revive the abandoned universal `<=14` proposal.

Joey photographed `E Kamaitachi Blade` with its `+1` wrapped onto the row below. Weapons
and shields carry a modifier from `-99` to `+99` and the item list draws it **after** the
name, out of the same 17 cells.

**Historical fixed-cell derivation (not the final VWF budget): 14 cells.** `4:$5D06`
emits the sign then the number through `4:$5CDC`,
whose `ld b,$02` suppresses at most one leading zero -- so `+1` costs 2 cells and `+99`
costs 3, and both charge `$C6DC` like any other cell. 17 - 3 = 14.

**Measured against all 145 item names, exactly ONE breaks it:**

| name | cells | class |
|---|---|---|
| ~~`Kamaitachi Blade`~~ -> `Kama Itachi` | ~~16~~ 11 | weapon (index 11) — **FIXED 2026-08-04** |

Every other weapon is <= 14 and every shield is <= 14 (the longest, `Rustproof Shield`
family aside, is exactly 14). The 18 other names over 14 cells are bracers, scrolls, herbs
and food, **none of which take a `+N`** -- so they are not affected and must not be
shortened for this.

**Settled by the official English rather than by fitting.** Joey pointed at Shiren 6's
weapon list, where the same weapon is `Kama Itachi` -- transliterated, two words, **no
category noun**. That is 11 cells, so it survives `+99` with room to spare, and it is a
better name than any shortening-to-fit would have produced. Photographed as
`E Kama Itachi+1` on one row.

> **ALIGNED TO SHIREN 6 on Joey's instruction, 2026-08-04** -- "go with the shiren 6
> naming for all except minotaur axe". Ten names changed:
> `Dotanuki`->`Doutanuki`, `Manjikabra`->`Manji Kabura` (ours was a misreading of
> マンジカブラ), `Kaburasutegi`->`Kabura Sutegi`, `Dragon Killer`->`Dragonkiller`,
> `Fuma Blade`->`Kajin Fuuma`, `One-Eye Killer`->`Cyclops Bane`,
> `Drain Buster`->`Drain Slayer`, `Sure-Hit Sword`->`Accurate Sword`,
> `Fuma Shield`->`Fuuma Shield`, `Spiral Shield`->`Rasen Fuuma`. Five item descriptions
> that quote those names were re-wrapped with them; `lint_en`'s `term_ignored` named three
> of the five and the other two were caught by hand.
>
> **HISTORICAL 2026-08-04 DECISION RECORD; THE 14-CHARACTER FIT REASONS ARE SUPERSEDED.**
> The semantic/taste decisions remain Joey's, but “over 14” is no longer a visual verdict.
> All five Shiren 6 equipment variants below physically fit the 128px item payload with
> representative widest signed suffix `-99`; four cross the current 17-source-character
> item stager and therefore need
> engineering, not automatic rejection. Runtime dialogue consumers remain to be censused.
>
> | ours | Shiren 6 | current measured status |
> |---|---|---|
> | `Minotaur Axe` | `Axe of the Minotaur` | Joey preferred ours; `-99` is 111px/14 tiles but 22 source chars |
> | `Sickle` | `Sickle of Salvation` | restores 成仏 meaning; `-99` is 99px/13 tiles but 22 source chars |
> | `Todo Shield` | `Walrus Stopper` | `-99` is 87px/11 tiles and exactly 17 source chars; terminology still touches the Todo family |
> | `Evasion Shield`, `One-Use Shield` | `Watchful Shield`, `Break-Off Shield` | `-99` variants are 85/88px but 18/19 source chars |
>
> One more that fits either way and is pure taste: `Battle Counter` (14) for バトルカウンター
> against Shiren 6's `Counter Shield` (14). The Japanese differs (バトルカウンター vs
> カウンター), so it is not the same name, and ours is the faithful transliteration.
>
> ~~Every weapon and shield is <=14, therefore nothing overflows with `+99`.~~ This was a
> fixed-cell conclusion. Current shipped variants are now checked from actual Dot pixels,
> painted tile footprints and the 17-character source stager by `fontaudit.py`.
>
> **Shiren 6 names weapons without a category noun**, which is worth knowing before the
> remaining weapon names are revisited: `Katana`, `Doutanuki`, `Manji Kabura`,
> `Kabura Sutegi`, `Dragonkiller`. Ours read `Dotanuki`, `Manjikabra`, `Kaburasutegi`,
> `Dragon Killer` -- and `Manjikabra` looks like a straight misreading of マンジカブラ.
> The current shipped variants pass the new physical/source audit, so these remain
> consistency and taste questions. `Axe of the Minotaur` is no longer rejected merely for
> being 19 bare characters; its 22-character `+99` source path and dialogue consumers need
> engineering review if Joey ever prefers that name.

**Do not add the proposed `<=14` lint now.** `lint_en.counter_overflow` still correctly
protects the current staff/pot `[NN]` source path, but a sibling weapon/shield check must
wait for the remeasurement above. The eventual check should key equipment on its index in
the name table (weapons 0-17, shields 18-33; `13:$554A` confirms that boundary), then
validate both the measured Dot-pixel result and every runtime source-staging contract.

> **ALREADY HANDLED, so nobody re-opens the suffix class:** pots take `[NN]` exactly like
> staffs and `carries_counter` covers both. Current variants pass both the 17-source-glyph
> guard and `fontaudit`'s 128px physical check. A future crossing requests engineering;
> it does not automatically require a shorter name.

### ~~Session 3b — clean up the name-entry grid (independent, zero bytes)~~ — **DONE 2026-08-10**

The shipped rows are the continuous layout in the current completion block above. All 75
selectable cells are unique and intentional; the right block contains `y`, `z`, 13 chosen
punctuation marks and digits 0-9. No ROM space, box geometry, cursor mapping or save-format
change was needed. `build.py` now also forbids DTE for box 12 because selection reads a raw
byte even though drawing can expand one. Normal/shuffled both-page probes, `Shiren` and
`Keyaki` save paths, `newgamesmoke`, `structspill` and the complete build pass.

**Historical priority note follows.**

> **Joey asked on 2026-08-04 whether this is next. Recommend NOT.** It is small, safe and
> genuinely optional — the naming screen already *works*, takes six characters, and the two
> bugs that made it draw wrong are fixed. Session 4 is 340 strings of text a player reads
> constantly, and it is the block the frozen glossary was frozen *for*. Take 3b when you
> want a short session, or when someone is annoyed by the grid; it will not get harder for
> waiting, and it blocks nothing.

**Joey's decision, 2026-08-04:** remove the second-page behaviour rather than build it, and
tidy the grid. That closed the one design question and made this the small, safe job now
completed above.

> **This does NOT mean un-aliasing box 13. Do not touch `script/box_alias.tsv`.** Box 13's
> 116 freed bytes at `31:$42DB-$434E` are **spent**: they are the largest free run bank 31
> has, and they are what lets item category boxes 33 and 34 keep the word "Staff" (24
> contiguous bytes against a next-largest run of 23). Un-aliasing takes bank 31's endgame
> margin from **+84 to -32** and breaks two other screens. The alias stays; what goes is
> the *promise* the `CAPS` key makes.

**Pre-implementation analysis, retained:** most of the work was already done. Disassembled
2026-08-04, `31:$4186`:

```
31:$4186  ld a,[$C6F3]     ; the CAPS flag
31:$4189  bit 7,a
31:$418B  jr nz,$4192
31:$418D  ld hl,$4273      <- page 1
31:$4190  jr $4195
31:$4192  ld hl,$4273      <- page 2, THE SAME ADDRESS, because of the alias
```

**Both arms already loaded the same table**, so selection was single-page. The old key only
forced a redraw of a box with identical rows. This was the retained pre-implementation plan:

1. **Retire the `CAPS` label.** It is a header cell that promises a mode which does not
   exist. Either blank it or give the cell to something useful. Header labels are mapped by
   cursor column — 0-3, 6-8, 10-12, 15-17 — so this is a picker change as well as a text
   change; do not just overwrite the word.
2. **Optionally make the toggle inert**, so the key does not redraw at all. The `jr nz` at
   `31:$418B` is the same shape as the `4:$5EE8` fix name6 made: making a branch
   unconditional is one byte and stops two paths drifting apart.
3. **Re-lay-out rows 1-5.** The exact bytes as built, dumped from `31:$4273`:

```
row 1  0B 0C 0D 0E 0F 00 24 25 26 27 28 00 00 39 3A 3B 3C 3D   ABCDE Zabcd  uvwxy
row 2  10 11 12 13 14 00 29 2A 2B 2C 2D 00 00 3E 3F 40 41 7B   FGHIJ efghi  z.,'<7B>
row 3  15 16 17 18 19 00 2E 00 2F 00 30 00 00 01 02 03 04 05   KLMNO j k l  01234
row 4  1A 1B 1C 1D 1E 00 31 32 33 34 35 00 00 06 07 08 09 0A   PQRST mnopq  56789
row 5  1F 20 21 22 23 00 36 37 38 C2 C3 00 00 7C 7D 7E 7F 80   UVWXY rst<C2><C3>  +<7D>[]?
```

**Four cells hold codes that are not in the English page at all** — `$7B`, `$C2`, `$C3`,
`$7D` — so they draw leftover ROM symbols. And the punctuation that *is* drawn is
arbitrary: `+ [ ] ?` are in the grid while `- ! ( ) : /` are not, and `$42`, the hyphen
`latinfont.py` actually draws, appears nowhere. **Decide the punctuation set deliberately**
rather than inheriting whichever kana slots happened to be there.

**Exit:** `gridprobe.py` 0 wrong on every row (and on the page-2 alias, which still has to
read what it draws), `namerun.py` still round-trips `Shiren` and `Keyaki`, and a photograph
of the screen **in its initial state** — that is the class of bug that shipped twice in
session 1, and a screenshot taken after typing looks fine when it is not.

### ~~Session 2 — VWF for the composer~~ — **DONE 2026-08-03**

`tools/vwf.py`, applied by `build.py` (bisect control: `--no-vwf`). **A composer line holds
24 characters instead of 18**, in the same 18 tiles. Full account in
`docs/archive/HANDOFF_VWF.md`,
which now opens with the result; what follows is only what a later session needs.

**Evidence:** `build/vwfshots/pool_dungeon_s1_009.png` against
`build/vwfshots_base/pool_dungeon_s1_009.png` — the innkeeper's *"Ah, you woke up at last!
You were crying"*, same save, same frame, drawn both ways.

**A uniform 6px pen, not a per-glyph width table.** The gain is 24 characters against a
true-proportional 25 — one character — and the uniform pen buys back three things: 72px is
divisible by both 6 and 8, so the half-line boundary lands on a glyph *and* a tile edge;
the cell budget stays a CHARACTER count, so **`dte_emit` needed no change and the DTE
collision is closed rather than solved**; and the `$CF38` buffer bound still holds.

**The plumbing question that gated it is settled, by trace.** `$C006` is a VRAM transfer
queue — `dw destination` then a payload — read by two bank-0 stack-pointer blitters that
disagree about the payload size (`0:$10A0`, 22-byte slots, tilemap rows; `0:$11C5`,
66-byte slots, tile data; `3 x 22 = 66`). Both readings in the old brief were right.

**Timing did not move.** `msgdur.py` gives the same four numbers on both builds — 17 boxes,
total 3382, median 189, min 17, max 628 — on the remade `saves/dungeon.state`, whose
seeded walk reaches real combat. The status screen and the title → file menu sequence are
**pixel-identical** against `--no-vwf`.

> **The ITEM DESCRIPTION screen is a SEPARATE renderer and is still fixed width.**
> `4:$49A7` far-calls `13:$7E49`, which composes into `$C616` and is drawn on the tilemap;
> it never reaches `13:$43B8`. Measured: `helpshot.py --topic N` is identical on both
> builds. **That is 122 of the 340 strings in session 4's batch** and they are budgeted at
> 18 cells, not 24.
>
> **`helpshot.py` calls this the "help/tutorial" screen and that label is wrong.** Every
> one of the 122 entries in table `13:$554A` is an item: a name in dashes plus two or three
> lines of what it does — `−もっこうのたて−` "equipping it raises defence / it does not
> rust", `−しんきしょくりょう1−`, `−くちなしのまきもの−`, `−しんきつえ2−`. It is the
> item info text, and it should be translated with the glossary's item names, not as prose.

**`latinfont.py` now draws the digits and ten punctuation marks**, because the ROM's own
glyphs for them ink columns 1..6 (or 0..7) and a 6px pen would clip them. Every code an
English string can contain is asserted to ink no further than column 4, at build time and
by `latinfont.py --audit`.

**How far outside the composer that shows — MEASURED, and it is less than a first draft of
this section claimed.** `build/oldglyphs.gb` is the shipped ROM with those 20 glyphs
reverted to the ROM's own, which isolates the font change from everything else:

| screen | result |
|---|---|
| the in-dungeon status bar (`HP 15/ 15`, `BELLY 100/100`) | **pixel-IDENTICAL** — it does not draw from `13:$7680` |
| a dungeon floor, 400 frames | **pixel-IDENTICAL** |
| the status SCREEN (Gitan / Floor / Str / Exp) | differs |
| the log list | differs |

**The whole visible difference is the ZERO.** The ROM's `0` is a plain oval and reads as a
capital `O` in an English script — `0 Gitan` drew as `OG`. The redrawn one has a diagonal
through it. `build/glyph_before_after.png` is the two side by side. Joey looked at the
status bar and correctly saw no difference; there is none there.

### ~~Session 3 — the glossary~~ — **DONE 2026-08-04. 391 names, not 388.**

`script/glossary.tsv` is frozen, `build.py` loads it (`--no-glossary` is the bisect
control), and `tools/lint_en.py` enforces four things: `legacy_cap_unreviewed`, `glossary_split`
(one Japanese name rendered two ways), `glossary_collision` (two names the player cannot
tell apart) and `term_ignored` (prose that names a monster and does not use the frozen
rendering). All four have negative tests; `term_ignored` found a real clash on its first
run — `おかみ` was frozen as *Landlady* while the shipped innkeeper speech had already been
reviewed as *Innkeeper*, and the glossary is what changed.

**House style, decided by Joey 2026-08-04:** modern official-Shiren English — plain and
meaning-first, so `ひとつめゴロシ` is `One-Eye Killer` and not `Hitotsume Goroshi` — but
Aeon Genesis' **category nouns**, so the sibling SNES project agrees where it is cheapest:
Herb / Bracer / Staff / Pot / Scroll. `~/Documents/Workplace/Shiren/shiren-revamp-fixes/
text/{itemnames,enemynames}.asm` is that project's table and it was the reference.

**388 was an undercount, and the missing three are a bug worth knowing about.**
`きみょうなはこ`, `エーテルもどき` and `アイアンヘッド` — one item and two tier-1 monsters,
all three reached by live pointer tables — were **not in `script.json` at all**. `き` is
code `$11`, which is `ld de,nn`, so a linear scan read the kana as an instruction, and
`extract.py` then discarded the strings for "containing a pointer operand". Fixed in
`immediate_refs`: a load that starts inside a known string is text. It suppresses exactly
2 of 249 immediates, both `ld de` in bank 11, and `dis.boundary_votes` cannot help because
it needs an instruction stream to reason about and a kana block has none.

A second fix fell out of the same area. `11:$4847` — the dakuten of `ヒツジのえのまきもの`
plus the seven bytes after it — was kept as a "string" because a six-entry cross-bank
"table" in bank 10 (whose other five entries all hold one pointer) appeared to reference
it. It **overlaps `11:$4844`**, so the build failed `BADREF` the moment Sheep Scroll was
translated. A string cannot begin with a combining mark; that is a codec fact and it does
not take a waiver from a reference.

**Also fixed: `reloc_verify.py` was about to become noise.** Its raw-copy arm compares a
redirected read against the ORIGINAL Japanese with no skip for translated strings — a
hazard `check_render` has documented since it was written. 391 names landing in bank 11
took it to *396 mismatches on a build whose `--no-glossary` control was clean*. It now
skips and counts them, and its docstring says how to get real coverage back.

**Historical fixed-width measurement, superseded for Dot policy:** the inventory list box
is 18 tiles and the old raw path had 17 source cells after its cursor. A 16-cell name was
photographed complete in `build/glossary_widest.png`, but that did **not** prove 16 was the
ceiling on the proportional menu or every dialogue substitution. Session 3e now measures
the 128px payload and current suffix variants separately.

**17 names are Joey's call** and are marked in the review page rather than in the file:
the ones where the cap forced something out (`Hiken Kaburasutegi` 18 → `Kaburasutegi`,
`Monster House Scroll` 20 → `Ambush Scroll`, `Aquamarine Bracer` 17 → `Aqua Bracer`) and
the ones that are taste (the タヌキ tier words; `Gazer` vs `Gaze`, as confusable in English
as `ギャザー` vs `ゲイズ` is in Japanese). Changing one is a cell of `glossary.tsv`, after
which `lint_en.py` names every prose string that has to follow.

<details><summary>The brief as written before it was executed</summary>

The highest-leverage translation session, and the one that must come before prose. VWF has
landed, so the caps it is written against are settled: **`NAME_CAP` 14, `ITEM_CAP` 16**
(§4). Expect a handful of the longest names still to need rewording — `Blade of
Kamaitachi` is 19 — but a handful, not the 34 the fixed-width caps would have refused.

**Why before the prose:** `こんぼう` appears as an item name, in help text, in combat lines and in shop
dialogue. Translated batch by batch it becomes Club / Cudgel / Stick, and review cannot
catch that — catching it means holding 1,419 strings in your head. Translate the names once,
freeze them, feed them to every later batch as a constraint.

* Translate all 388 (bank 11's `$4537` / `$4FC4` / `$4A6C` / `$4A38`).
* Write them to `script/glossary.tsv`, and add a **glossary-adherence check to
  `tools/lint_en.py`**: if the Japanese contains a glossary term, the English must use the
  frozen rendering.
* Add two checks that do not exist yet: **name collisions** (388 English names must be
  distinct) and **menu box width** (a name is rendered in a box sized by
  `script/box_geometry.tsv`).
* Joey reviews the 388 as rendered boxes.

**The cap this is written against comes from session 2, not from §4's fixed-width
numbers** — see §4. Expect a handful of the longest names to need rewording even with VWF
(`Preservation Pot`, `Blade of Kamaitachi`); expect Joey to want a say in those.

**Exit:** `script/glossary.tsv` frozen and reviewed; lint enforces it; every name inside its
cap and its box.

</details>

**One thing the brief asked for was not built, deliberately.** It wanted a *menu box width*
check driven by `script/box_geometry.tsv`. That file only lists boxes with ROM text, and the
inventory list is not one — it is drawn at runtime from the name table, so there is no row
in it to check against. What replaced the check is a measurement (`build/glossary_widest.png`,
above): the box holds 17 cells and the cap is 16, so the cap is the binding constraint and a
second checker would only restate it. If a name is ever rendered in a box narrower than that,
this becomes real work again — `tools/menushot.py --sweep` is how you find which box.

### ~~Session 3c — the item verbs~~ — **DONE 2026-08-04**

Joey's call: `Sip → Drink`, `Arm → Equip`, `Doff → Remove`. **They cost no engineering**,
and the reason is worth reading before you believe a comment in a translation file.

`script/en.tsv` said, in a comment: *"Box is 4 cells wide — confirmed on screen: 'Throw'
wrapped and 'Place' truncated to 'Plac'. Everything here is therefore <= 4."* That was true
when it was written and had been false ever since: it measured the **Japanese** box, and
`script/box_geometry.tsv` had already widened boxes 6 and 39 from `x=13,w=5` to `x=9,w=9`.
The budget is **8 cells**, not 4. `Drink` is photographed in `build/verbs_herb.png`;
`Equip` (5) and `Remove` (6) fit the same box but are not photographed, because the save
state carries no weapon or shield.

Bank 30 absorbed +3 bytes (DTE compressed the rest) and still projects `+12 spare`.

> **A stale measurement in a comment is worse than no measurement**, because it is quoted
> rather than re-derived. This one would have made the next session refuse Joey's verbs as
> impossible. The comment now says what the box IS and what changed it.

### ~~Sessions 4+ — bank 13 system text and item descriptions~~ — **DONE 2026-08-04. 341 strings.**

**Bank 13 is translated end to end.** The 8 strings that still have no English are
extraction false positives (`ア↓イ2アF`), not text. Also done: the 13 shared lines at
`11:$55AC`, because they are description LINES and nothing else reads them.

**The two budgets were real, and the tooling did not know about one of them.**
`dialogue_preview.py` measured *all* of bank 13 with the composer's 24 cells and 3 lines.
The item-description screen is box 7 of bank 31's tilemap renderer — descriptor `31:$4221`
= `x=0, y=3, 5 rows, w=$12`, source `$C616`, row 1 the item name, `13:$7E49 ld b,$04` the
line budget. So **18 cells and FOUR lines**, and the old model was wrong in both directions
at once: it would have passed a 24-cell description that loses six cells on screen, while
calling **51 boxes the game itself ships** `box_too_deep`. Fixed first, before a word was
translated; `geometry_for()` picks, and `--selftest` now asserts both halves.

**`<cF0:xx>` is inline TEXT, not a screen effect.** On this path it far-calls `11:$7E26`,
which pastes the string at `11:$55AC + 2*arg` into the buffer at the current position, no
break either side — so it costs its whole expansion. The wall is the proof: charging it
properly puts **70 Japanese lines exactly on 18 with none over**; charging it zero, which
is what the file used to do, drops that to 39.

**`13:$57AB` was never a string, and it cost a `BADREF`.** It starts two bytes inside
`13:$57A9`, splitting かいしん in half, and the build failed the moment the Minotaur Axe
description was translated — exactly what `11:$4847` did in session 3. Its "reference" was
`6:$56B9`: one $57AB then seventeen identical $57E2. **A table whose entries are all one
value cannot be a pointer table** — indexing it selects nothing. Across all 39 candidate
tables the split is clean (19 have ≤2 distinct entries, 20 have ≥4, none has 3) and the
rule reproduces a judgement `extract.py` already made by hand: `10:$4663`, the table behind
`6:$472F`'s MANUAL_DROP, is six identical pointers.

> ### TWO THINGS LEFT FOR A LATER SESSION, both found here and neither blocking
>
> **1. `11:$5848` will do the same thing to session 5.** It is nested 69 bytes inside
> `11:$5803` and is kept because something "references" it — `9:$6FCD`, whose words are
> `5848 4410 5A50 4410 5C58 4410 …`: a striding data structure in a bank the extractor
> itself calls a junk source, in which `$5848` looks like a coincidence. It has 4 distinct
> entries of 6, so the new rule deliberately does **not** touch it. But `11:$5803` is
> village dialogue, and the day it is translated the inserter will place both strings and
> one will overwrite the other. Settle it *before* translating that conversation, not after
> the BADREF. `build.py`'s "legitimate mid-conversation entry point" comment rests on this
> reference and would need rewriting too.
>
> ~~**2. Eighteen other weak tables are still believed.**~~ **RETRACTED THE SAME DAY, and
> this is the most useful thing in this document.** Scoping the rule to nested starts was
> wrong. Joey play-tested the build and found an equipped shield reading `Shield 0` where
> the Japanese ROM reads `9`: `10:$46B0` and `10:$46C6` are bank 10's numeric ITEM STATS,
> read as pointer tables, and build.py rewrote **25 bytes of them**. `table_is_real` now
> applies `distinct >= 3` generally and bank 10 is byte-identical to the original again.
>
> **It was corrupting item BEHAVIOUR, not just a displayed number.** Unequipping that
> shield also played a pot animation and printed "A Pot can't go in a Pot." -- the item was
> misclassified, so the game ran pot code on a shield. Both symptoms cleared with the same
> fix: the message queue receives one push where it used to receive two, the Japanese ROM
> on the same save prints only `ヒャッキのたてをはずした`, and the fixed build prints only
> `Removed Hyakki Shield+1`.
>
> **I called that symptom "original game behaviour" and it was not.** The reasoning error is
> worth more than the bug: I hooked the queue, saw `13:$4706` pushed, found `ld bc,$4706` at
> `6:$50C2` in the untouched ROM, and concluded the original does it too. But `6:$50C0` is
> the *legitimate* pot-in-pot routine -- it exists in every copy of the game and is supposed
> to be unreachable from a shield. **Proving a code path EXISTS in the original is not
> evidence that it is TAKEN in the original.** The test that settles it is the one Joey
> ran and I did not: perform the same action on the untouched ROM and look.
>
> **The check that would have caught it did not exist, and still does not.** `--shuffle`
> and 12 crash seeds were green throughout, because corrupting a stat table crashes
> nothing; the reference verification proves a STRING is reachable and cannot prove the
> site was ever a pointer. The cheap detector is the one in §1: **diff the built ROM
> against `_base_expanded.gb` and require every rewritten byte in a game-logic bank
> (2, 5-10, 12) to be a known message push or a declared patch.** Bank 10 must be zero.

**Evidence, on the real renderer rather than the model** — `build/help_t8.png` (Pickaxe,
four 18-cell lines), `build/help_fusion_p2.png`, `build/help_bracer.png`, and
`build/combat_1395.png`, which is the composer in the dungeon drawing `Defeated Rat
Minion! / Got 3 Exp.` from two fragments with a frozen glossary name substituted in.
`helpshot.py --topic N --unit M` reaches any description; no walk seed does.

<details><summary>The brief as written before it was executed</summary>

Take this before the village prose. It is formulaic (combat lines, status messages, the item
descriptions), it benefits most from a frozen glossary, and it contains **the tightest cell
budgets in the game** — some lines leave only 6 cells for a substitution.

**It is TWO budgets, not one, and that is the trap.** Combat and status lines go through the
composer and get VWF's 24 cells. **The 122 item descriptions do not**: table `13:$554A` is
drawn by `13:$7E49` on the tilemap and is **still 18**. Split the batches on that line and
do not let a 24-cell habit leak into the descriptions.

* Work in batches; run `lint_en.py` and `dialogue_preview.py --check` after each.
* The item descriptions are an item name in dashes plus two or three lines of what it does,
  reviewable with `python3 tools/helpshot.py <rom> --topic N`.
* Combat lines: `shiren-gb-var-cell-budget` is the memory to read first.

</details>

**What the brief did not anticipate**, and what a later session should take as the lesson:
it said the descriptions "are still 18" and it was right — but nothing *checked* 18, and
a green `dialogue_preview.py --check` would have said so either way. **Knowing a budget and
enforcing it are different things.** The first hour of this session went into making the
tool able to be wrong.

### ~~Session 5 — in-place village and story dialogue~~ — **DONE 2026-08-05. 355 strings.**

**It was 355, not the 323 estimated here** — bank 14's 204 plus bank 11's 151 from
`11:$56DB` up. (The 21 bank-11 strings *below* `$56DB` are equipment ability lines, not
prose; they belong to session 6.) The battery is green on all 822 translated strings.

> **AND IT IS NOT FINISHED, because the extractor is missing 7.9 KB more.** See the box at
> the top of this file — session 5b. Everything below describes what was done to the
> extracted script.

**Three things landed with it that outlive it:**

* **`tools/wrap_en.py`** — drafts are SENTENCES, the tool makes lines. It owns `<br>`, the
  leading-space indent, the three-line box and the `<end>`s. `script/prose_draft.tsv` keeps
  the drafts, so the next geometry change is `wrap_en.py --apply`, not a session. That is
  the direct answer to the re-wrap problem this session inherited.
* **`<end>` is a `wait here`, not a terminator, and it is now measured.** All 120 `<brk>` in
  banks 11/14 are preceded by `<end>`; **no** string ends with one; and `13:$40B8`, the only
  reader of `$CFC4` in the whole ROM, tests it once with `and a`. So presence matters and
  position does not, and only 23 of the 68 multi-box strings ask their last box to wait.
* **The speaker-tag rule** — see §4.

**The 17 strings the old brief said to re-wrap were 3.** Measured: only `14:$5047`,
`14:$5106` and `14:$5127` were multi-line, 24-cell and still wrapped for 18, carrying 207
idle cells over 27 lines. The rest of the old 377-cell figure was single-line messages,
where "idle" is just a short sentence and re-wrapping reclaims nothing.

**Length was free, as promised** — 355 strings redirected into the pool with 458 KiB spare.
Cells still bind: 24 a line, 3 lines a box.

#### Photographing village dialogue is SOLVED, and it is how the extraction gap was found

The old note said reaching this text was the known difficulty. It is not any more, and no
button script was needed:

1. `gbrun.py --dte-scan --state saves/dungeon.state --walk-seed 1` reports which `loc`s the
   seeded walk actually reads. That is how `14:$52C7` was identified as a reachable village
   string carrying no mandatory tokens — the ideal vehicle for a mock-up.
2. Hook the bank-14 stager at **`14:$400D`** to know when a village message starts, wait
   ~150 frames for the typewriter, and screenshot.
3. To read what the game *actually drew*, dump the composer's staging buffer at **`$CF07`**
   whenever `WY` (`$FF4A`) is above the status bar. That is the step that proved the English
   renders correctly AND that two lines on screen came from strings nobody had extracted.

`build/speakertag_choice.png` and `build/session5_village.png` were both produced this way.

> **A `--no-vwf` build is no longer a valid control for `msgdur` or `gbrun --compare`.**
> The battery says the two must match; they no longer can, and it is not a regression. A
> `--no-vwf` build draws 18 cells, this script now writes lines up to 24, so the control
> truncates them, draws fewer characters and the typewriter runs short — the walk then
> diverges. Verified: the pre-session script matched exactly (16 boxes, identical totals);
> the three bank-13 lines the walk reads are unchanged at <= 18 literal cells; `14:$52C7`,
> newly translated, has lines of 22/24/23/24. Messages now stay on screen **longer**
> (median 245 frames against 189), which is the safe direction.

### ~~Session 6 — fix the column-19 spill~~ — **DONE 2026-08-05**

Full diagnosis is the box near the top of this file. In one line: the typewriter appends one
tilemap entry per **character** and nothing clamps it to the row's 18 tiles, so a line over
18 characters runs its indices into the next row's tiles and column 19 (which is on screen)
shows the start of the next line.

* Entry for character N must be `base + ((6 * N) >> 3)`, not `base + N`.
* `13:$4523` is **not** the culprit — it writes a fixed 18 and is correct. The per-character
  append site is not located yet; find what writes a single incrementing byte to `$9C41`
  onward, one byte per frame, while the text types.
* Reproduce with `tools/gbrun.py` from `saves/dungeon.state` and diff `$9C00-$9DFF` per
  frame — that is how it was characterised, and it is a two-minute loop.
* **Regression test**: assert no line writes past the row's 18th tile. This is cheap and it
  is the check that was missing; `vwf.py --selftest` is where it belongs.
* Do **not** re-wrap the script to 18 cells to dodge it.

### ~~Session 7 — extraction completeness~~ — **DONE 2026-08-05**

Full write-up is the box near the top. One line: `regions.py` duplicated `codec.py`'s
character table and the copy had been stale since week one. `tools/coverage.py` is the check
that was missing and it is now in §1 and in `build.sh`.

### ~~Session 8 — translate what session 7 found~~ — **DONE 2026-08-05. 161 strings.**

**1212 → 1373 translated; 207 left → 46.** Bank 14 is 334/335 and bank 11 623/643. The
162nd string, `14:$7EE6`, is 294 cells of decoded garbage that nothing draws —
`dialogue_preview --selftest` names it and says why. Everything else in the two dialogue
banks is English.

What landed, none of it ever seen in English before: the **whole shop** (`14:$4031`
onward, the haggling, the price prompts, the monster-house warning), the **Shrine
Priest's help menus** (`14:$4303`-`$45D4` — dash, diagonal walk, the Items menu, arrows,
the map, swapping with a companion), the **Kuyo Pass road picker** (`14:$4638`/`$465B`/
`$467F` — this is Joey's "Normal is still Japanese"), the four **signboards**, the
**voice in the well** and Koppa's reunion, **Dragon's Maw** and Koppa working out what the
shrine's name means, **Yoshizota's confession** and the transformation, the **feast** and
the Chief on the Kuyo Pass monsters, the **ending farewells**, **Kinji and Keyaki at the
shrine**, **Chomomo**, and all four **companion recruitments** (Pochi, the Rooster,
Tanmomo, Baby Mamel).

#### The blocker that had to be cleared first, and it was a real one

**`codec.ARITY` was hiding a real character inside `<cF0:xx>` in banks 11/14** — the third
instance of "a rule derived from one of two dispatch tables and applied to both", after
sessions 7 and 8b. Seven `$F0` sites, six strings, every one of them in this batch:
`<cF0:56>ギ` is **ナギ**, `<cF0:49>スリ` is **クスリ**, `<cF0:EA>` is **`<name>`**. Carrying
the token into an English line would have printed a stray ナ or ク in front of it, and
`lint_en`'s token parity would have *insisted* on it.

**It was measured, not argued** — `tools/gbemu.py` now runs the ROM's own staging loop
(`13:$6893`) over `code + あいう` and reads the `$CF07` buffer back. Full table and the
`$EC` loose end it also closes: `FINDINGS.md` → "The arities are MEASURED". `FINDINGS.md`
had closed `$F0` in July with *"never appears in banks 11/14, so its difference is
inert"* — true of the script as extracted then, and **a fact about the data written as
though it were a fact about the ROM**.

#### Things a reviewer should know before reading the boxes

* **`Chomomo` is a new name and it is NOT in the glossary**, because the glossary is keyed
  on the NPC name table at `11:$4Fxx` and チョウモモ has no entry there. Keyaki names the
  shrine cat after Tanmomo (`14:$6EF6`), so it is built the same way. **Joey's call.**
* **`Kid Tank` is the glossary's**, and the lint enforced it: `コドモせんしゃ` in
  `14:$4905` is a monster name, not "child warriors".
* **The speaker-tag rule bit once, correctly.** `14:$4B47` has Yoshizota *mentioning* the
  Chief, and a mention is not an attribution, so it reads `Village Chief` in full.
* **`11:$537F` is the one to eyeball on a screen nobody reached.** `：ふうらいの ` is a
  log-menu label ending in a space the name is drawn after; the row is
  `=: Log of<$00>`, because `load_draft` strips a real trailing space and `<$B4>` is not
  available (space is `$00` in both fonts, and a `$92-$DF` escape is a build error).
  Worth a look on the log/erase screen.
* **Boxes went up, deliberately.** 51 pages wrapped past three lines and every one now
  carries an authored `<brk>`, per `TRANSLATING.md` §1 — a clean `wrap_en` run has no
  `auto_split`, and it has none.

#### **HAND JOEY THE BUILD. These are the screens.**

The battery is green and the battery has never found any of the four defects Joey has.
In rough order of how early a player meets them:

1. **The shop** — buy, sell, haggle, and try to buy with too little money.
2. **The Shrine Priest**, all three help menus and all nine answers.
3. **The Kuyo Pass road picker** — the one he has reported for several sessions.
4. **The four signboards**: village entrance, the Totoya, the shrine, Dragon's Maw.
5. **The well**, Koppa's reunion, and Dragon's Maw with Yoshizota.
6. **The four companion recruitments**, and the "already have a companion" variants.
7. **The feast, the farewells and the ending** — the longest untested stretch.

### ~~Session 8c — box 48, the "Normal" difficulty text~~ — **DONE 2026-08-05**

**Joey's ruling, and it was the right one: no text location may be permanently
untranslatable.** `script/en.tsv` had this box commented out with a confident write-up
saying it could not be done — 20 bytes, 16 cells, four dakuten, and no English string
consumes 20 bytes inside an 18-cell box. **Every number in that was correct and it was
answering the wrong question.** The byte count only binds a row that cannot MOVE, and
box 48 could not move only because extraction had pinned it **by mistake**.

`31:$755B ld bc,$4571 / call $028B` is a message-queue push, so `$4571` is a **bank 13**
address — `<cE0:2B>とっぷうだ！！` — and has nothing to do with bank 31's text.
`box_interior_targets` was reading the operand without asking what the code does with it;
`msg_push_kind` is the filter `immediate_refs` already used for exactly this. Six such
loads were pinning boxes **48, 50 and 51**. 5 pinned → 2, and the two that remain are real.

Photographed on the actual screen: **Easy / Normal / Hard all read English now.** The
Fei's Quiz header went with it, and its two written-into columns were measured off the
screen's own tilemap rather than guessed — the task number is right-aligned into cells
2-4 and the difficulty **stars** start at cell 13, which is what the first attempt's
`Difficulty` collided with. It reads `No  1  Rating★`.

> **The lesson is the one this project keeps re-learning.** A correct calculation about
> the wrong constraint is indistinguishable from a finished diagnosis, and it sat in
> `en.tsv` as settled fact until Joey refused to accept the conclusion. When a doc says
> something is impossible, check what makes it impossible before believing the sum.

### ~~Session A — the two screens Joey found by playing~~ — **BOTH FIXED**

**Both were found the only way this project has ever found this class of defect: Joey
played the build.** Neither was a translation error and neither was visible to any check in
§1 — the battery was green on both, and A1 stayed open for three sessions after being
diagnosed wrongly. **A2 fixed 2026-08-05; A1 fixed 2026-08-06.**

#### ~~A1 — THE TOWN SIGNS DO NOT RENDER LIKE THE COMPOSER~~ — **FIXED 2026-08-06. It was the REDIRECT, and it was 25 strings, not 6.**

**Joey gave the route and that is what cracked it**: *"start a new game, a new log; it loads
into the town and there is a sign immediately above the player — push up, then a."* Three
sessions had been unable to reach a signboard at all; four 20,000-frame seeded walks never
found one. It is one square from where a new log begins. That is now `saves/sign.state`,
built by `tools/mkstate.py`.

**The geometry was never wrong. The RESUME POINTER was.** `dialogue_preview.geometry_for()`
hands these strings 24 cells × 3 lines, and the previous note called that a guess the
screenshots falsified. Measured off the window map: **3 lines is exactly right** — a
`<cEC>` message composes three, `13:$6CB3 ld c,$00` then `call $6CE9` three times. The
transparent rows and the leftover text were a symptom, not the defect.

**What actually happened, and it is one instruction.** `13:$67F3` tests the first staged
byte for `$EC`; if it matches, `13:$6C73` re-derives the resume pointer as **`hl + 2`** —
`hl` still being the address the message came from — and stores it through `13:$6CA8`.
That store runs AFTER `13:$7589`, so it threw away the pool continuation the redirect had
just written and pointed back into the **middle of the 4-byte record**:

```
14:$41C2   E9 61 4D FF        resume := $41C4 -> `4D FF`  -> one `シ`, then stop
14:$41C2   EC 04 E9 61 4D FF  resume := $41C4 -> the record  -> "Moonlight Village"
```

So the fix is a LAYOUT rule, not a code patch: leave `EC arg` where the ROM expects it and
put the record at +2, which is precisely where `$6C73` is going to point. `pool.head_bytes()`
does it, `pool.starts_ec()` decides who gets it, and the pooled text no longer repeats the
prefix. Verified on the real screen, driven from a new game.

> **`pool.py`'s founding claim was "13:$7589 is the ONE gate", and it was measured about
> STAGING and then relied on for the POINTER.** Both facts are true; they are not the same
> fact. This is the fifth time this project has been bitten by two honest statements about
> two different things — see [[shiren-gb-uniform-table-is-not-a-table]]. `FINDINGS.md` →
> "`13:$6CA8` writes the resume pointer too".

**IT WAS 25 STRINGS, NOT 6, and one of them is a bug Joey has reported for several
sessions.** Every bank-14 string that opens `<cEC:xx>` and was redirected: the four
**signboards**, the **shop's buy/sell/haggle confirmations**, the **Shrine Priest's three
help menus**, the **well** and the **offering box**, the **three companion recruitments**,
and the **Kuyo Pass road picker in all three of its states** — `Easy / Normal / Hard` with
`(current road)` on a different one each. Session 8 translated that picker and session 8c
freed its menu labels; this is why it still did not read English on screen.

**Two things joined the battery, and the first is the one that matters:**

* **`build.py`'s `ec_prefix_lost`** reads the BUILT ROM and fails if a `<cEC>` string does
  not open with `$EC` at the address it ended up at. Confirmed to fire on exactly the 25
  by rebuilding with `head_bytes` stubbed out — it is not passing vacuously.
* **`tools/msgshot.py`** draws ANY bank-11/14 message on the real screen, by substituting
  the queued pointer at `13:$67ED`. That is what photographed all 25; reaching them by
  playing was the obstacle that kept this open.

Measured against a build with the fix stubbed out: `msgdur` identical (10 boxes, total
2563, median 250), and `gbrun --compare` from `town.state` is **pixel-identical** — the
change touches these 25 screens and nothing else. Battery green, including `--redirect-all`
and `--shuffle` with 12 crash seeds each.

> **Relocatable `<cEC>` strings are excluded from the pool, deliberately.** The in-place
> redirect works because `13:$7589` stages the record on the NEXT pass; a relocatable
> trampoline tests the MARK at `(hl)` before its loop starts, so a record two bytes in is
> invisible to it and the loop would copy `EC arg E9 lo hi FF` out as text. The two
> mechanisms genuinely disagree. All six such strings fit in place today, and `reloc_can`
> now says why rather than leaving it latent.

#### ~~A2 — FEI'S QUIZ HEADER: A SECOND COPY AT `4:$704E`~~ — **FIXED 2026-08-05**

**Joey's report, exactly: the header is English when you enter the quiz, and the moment you
move to a different challenge it stops being English — and going back does not bring it
back.** Reproduced and diagnosed 2026-08-05.

**The screen draws its header from TWO different places.**

| | source | state |
|---|---|---|
| on entry | box 30's text, `31:$4435` | extracted, translated — `No  1  Rating★` |
| on every task change | **`4:$704E`** | **never extracted, never translated** |

`4:$704E` is `1A 0C 00 00 00 2D 38 00 00 1F 38 0C 1E` + five spaces + `$BF` + `$FF`. That is
`だい   もん  なんいど` **with the dakuten bytes stripped and padded to the full 18 cells,
followed by the box's right-border tile** — so it is not a string at all, it is a
**pre-rendered tilemap row** the redraw copies straight out. The routine above it is the
one that draws the stars: `4:$703E ld hl,$C016 / ld a,$8A / ld [hl+],a / dec b / jr nz`.

Measured off the screen's own tilemap, before and after moving the task cursor:

```
on entry   N  o  __ __ 1  __ __ R  a  t  i  n  g  *
after      P  B  __ 1  1  i  t  __ __ U  t  B  T  * * *
```

The second row is those Japanese byte codes rendered through the **English** font, which is
what "no longer English" looks like.

**Why nothing caught it.** `coverage.py` asks whether every `$FF`-framed run in the SCRIPT
BANKS is extracted. This is in bank 4, and it is not framed as a string — it is 18 tilemap
cells and a border tile. Both of its defences are the wrong shape for it.

**How it was fixed.** `build.py` **MIRRORS** the box-30 translation into the row —
`QUIZ_ROW_AT`, applied beside the raw patches. It is a DERIVED copy, not a second
translation: edit `31:$4435` and the row follows. A hand-written second copy would have
gone stale exactly the way the first one did.

Three things make the mirror safe rather than another duplicate:

* it reads `plain[]`, not `final[]`, so a DTE-compressed string can never reach a row that
  is copied into the tilemap byte for byte and never passes an expander;
* it **guards on the original bytes** and reports `quiz_row_moved` rather than writing over
  whatever moved in, and `quiz_row_unfit` if the English is over 18 cells or holds a
  control code;
* it is declared to `logicdiff.py`, which took bank 4's unexplained column from 91 to 81.
  An explained write that reads as unexplained is how that check loses its meaning.

Measured on the real screen, driven through the real menu — the header now survives every
task change: `No 11  Rating★★★`. A byte-for-byte diff against a build without the mirror
is **10 bytes at `4:$704E` and the header checksum**, nothing else.

**Still to do, and it is the reason this class matters:** a pre-rendered tilemap row in a
code bank is a category no check covers. Sweep banks 0-10 for runs that decode as kana and
end in `$BF`/`$FF`, and see what else the game redraws this way. `coverage.py` cannot: it
scans `$FF`-framed runs in the SCRIPT banks, and this was neither.

> **This is the duplicated-table trap again, and it is the fourth time.** `regions.py` vs
> `codec.py` (session 7), the two dispatch tables (8b), `codec.ARITY` vs the dialogue path
> (session 8's pre-flight), and now a row of tiles that restates a box's text. Every one was
> two honest copies of the same fact that drifted. See [[shiren-gb-uniform-table-is-not-a-table]].

### ~~Session 9 — the weapon and shield SEALS~~ — **DONE 2026-08-06. 20 strings. Bank 11 is 643/643.**

> **The translation was the small half. `--check` was not measuring them at 24 cells — it
> was not measuring them AT ALL.** The brief below said to widen `is_help()`, which is
> scoped to bank 13, and that was correct as far as it went. But `build.py` and `--check`
> both gate on `is_dialogue()` first, and that returned **False** for every one of the 20:
> the seals have a `refs` entry (the table at `11:$5463`) and carry no control codes, so
> the last line of the predicate rejected them. A translation of any width, on any number
> of lines, would have shipped green. Both predicates are fixed, and `is_dialogue`'s
> docstring now says what it actually gates.
>
> **And the line budget was 4 in the brief and is 1.** `11:$7E40 ld c,$04` is four SEALS,
> not four lines of one seal — each string is copied `$FF`-terminated into the next row
> under the item name, so a `<br>` in one would eat the next seal's row and draw as a tile
> besides. `SEAL_LINES_PER_BOX = 1`, and `--selftest` falsifies it against the shipped
> Japanese: 20 strings, none of them broken, none over 18 cells, three exactly on 18.
>
> **ALL 20 ARE PHOTOGRAPHED — `build/seals_00.png` … `seals_16.png`.** `tools/sealshot.py`
> is new and it is the answer to "forcing dispatcher index 5 hangs", which is what stopped
> the last session. **The dispatcher was never the problem.** `11:$7E40` reads the item's
> seal ids from `$C6BE`, and a state not sitting on a melded item leaves junk there; a junk
> id is doubled into `$5463 + 2a`, so the copy starts at an arbitrary address and runs to
> the next `$FF` anywhere in bank 11 — straight past the 120 bytes `4:$49F5` cleared, into
> live WRAM. **It was not the screen that hung, it was the byte after it.** Supply the
> context (`$C6BE` the ids, `$C6BD` the count, `$C6BC` the scroll offset) and the real
> routine draws through the real renderer. Run it against `build/_base_expanded.gb` for the
> Japanese control.
>
> **Wording came from the item descriptions, not from scratch.** Bank 13's 122 descriptions
> already describe these same effects at greater length and are already reviewed, so
> `Deals heavy damage to Dragons` (13:$56C1) fixes `Strong vs Dragons`, `To one-eyed foes`
> (13:$57E2) fixes `One-Eyes` over "Cyclops", and `Cuts damage from explosions` (13:$5A2C)
> fixes `Cuts blast damage`. A seal and its description must not read like two effects.
>
> **Two wordings are worth Joey's ruling** and neither is a fit problem: `[Meat]` and
> `[Poison]` for `「にく」`/`「どく」`, where the game declines to explain itself and there is
> no glossary item to align to; and `Strong vs One-Eyes`, which is 18 of 18 cells.

**It is 20, not 23.** The three bank-30 rows this used to count as "item verbs" are
**EMPTY** — `30:$7EFC`, `$7EFD` and `$7F07` are a bare `$FF` each in the Japanese, pointer
slots with no text behind them, and there is nothing to translate. (The real item verbs,
Drink / Equip / Remove, landed in session 3c.) In the English ROM those addresses read as
text because the repack moved other strings into them; that is the allocator working, not a
gap. At this historical point bank 31's remaining 11 rows were assigned to Session 3b;
five visible box-12 rows were completed on 2026-08-10, leaving only six aliased page-2
records that no screen renders.

So the whole session is one contiguous run in bank 11 — the lines the item screen prints
under a weapon or shield. Item help, not prose, which is why session 5 left them:

```
11:$548B  17  ドラゴンけいモンスターにつよい      11:$5529   5  さびない
11:$549D  16  ゴーストけいモンスターにつよい      11:$552F   5  「どく」
11:$54AE  13  ひとつめモンスターにつよい          11:$5535  19  ドラゴンのほのおのちからをよわめる
11:$54BC  19  ステータスをうばうモンスターにつよい  11:$5549  16  うけたダメージを はねかえす
11:$54D0   4  「にく」                            11:$555A  14  まほうこうげきをはねかえす
11:$54D5   7  かべをほれる                        11:$5569  16  てきのこうげきがあたりにくい
11:$54DD  15  かならずこうげきがあたる            11:$557A  22  こうげきをうけるたびにつよさがさがる
11:$54ED  15  かいしんのいちげきがでる            11:$5591  19  ばくはつのダメージをすくなくする
11:$54FD  21  まえ3ほうこう 1どにこうげきできる    11:$55A5   6  ぬすまれない
11:$5513  10  おなかがへりにくい
11:$551E  10  おなかがへりやすい
```

#### THESE ARE THE SEALS (印) — and nothing was measuring them at all

**Joey asked what they were and the answer is why they look untouched in play.** They are
the seal/ability lines on a weapon or shield — `ドラゴンけいモンスターにつよい` is the
dragon-killer seal, `うけたダメージをはねかえす` the reflect shield, `かならずこうげきが
あたる` the always-hit. A plain item has none, and an item's own description comes from a
different table (`13:$554A`, 157 entries) that IS translated — which is why picking things
up in a playtest looks finished. **You mostly see these after melding.**

**Traced end to end, 2026-08-06:**

```
4:$49F5   dispatcher index 5 -- zeroes 120 bytes at $C616, de = $C616, then
4:$5736     stages the item NAME into the buffer -- that is row 1 of the five
11:$7E40    ld a,[$C6BC] -> b        the seal slot to start at
            ld c,$04                 FOUR SEALS, max -- one per ROW, not four rows each
            hl = $C6BE + b           the item's seal ids, $FF-terminated
            a = [hl]; sla a
            hl = $5463 + a           <- THE TABLE. 20 entries, this session's 20 strings
            copy [hl]..$FF into [de], terminator INCLUDED, then inc b / dec c
4:$4A0D   ld a,$13 / rst $08 ...     draws box $13
```

Box `$13`'s descriptor (`31:$4395`) is `x=0 y=3 rows=5 width=18 src=$C616` — **byte-for-byte
the same as box 7's** (`31:$4221`), the item-description box.

**So the budget is 18 cells and ONE line.** The four rows under the name are shared out one
per seal, so a `<br>` in a seal eats the next seal's row — and draws as a tile besides,
because this is bank 31's tilemap drawer and `$EF` is not a break to it. Measured, not
inferred: the Japanese has no seal that breaks, none over 18, and **three sitting exactly
on 18** (`11:$54BC`, `11:$54FD`, `11:$557A`). `dialogue_preview --selftest` asserts both
halves against the shipped script.

> ### ~~`geometry_for()` hands them `(24, 3, 54)`~~ — **it never got that far. FIXED.**
>
> The brief was right that `is_help()` is scoped to bank 13. It was wrong about the
> consequence, and the real one is worse: **`build.py` and `--check` both gate on
> `is_dialogue()` before geometry is ever consulted**, and that returned `False` for all 20.
> The seals have a `refs` entry (the table at `11:$5463`) and carry no control codes, so
> the predicate's last line rejected them. Not measured too wide — **not measured**.
>
> ```python
> if not r['refs']:                       # in-place text is dialogue by construction
>     return True
> return any(CONTROL_MIN <= b <= CONTROL_MAX for b in ...)   # <- the seals died here
> ```
>
> `is_help` now covers `11:$548B`-`$55A5` via `is_seal`, `is_dialogue` returns True for
> anything `is_help` claims, and `geometry_for` returns `SEAL_LINES_PER_BOX = 1` for a seal
> against `HELP_LINES_PER_BOX = 4` for a description. **Falsified before it was trusted:**
> a 22-cell seal reports `line_too_long` and a two-line one reports `box_too_deep`, both
> exit 1. `is_dialogue`'s docstring now says what it really gates, because the name has
> been describing something narrower than the job since the item descriptions joined it.

**PHOTOGRAPHED — `tools/sealshot.py`, and "index 5 hangs" was a wrong diagnosis.**
The dispatcher is fine. `11:$7E40` reads the seal ids from `$C6BE`, and a save state not
sitting on a melded item leaves junk there; a junk id is doubled into `$5463 + 2a`, so the
copy starts at an arbitrary address and runs to the next `$FF` anywhere in bank 11 — past
the 120 bytes `4:$49F5` cleared, into live WRAM. **It was not the screen that hung, it was
the byte after it.** Supply the context and the real routine draws through the real
renderer:

```sh
python3 tools/sealshot.py build/shiren_en.gb --all --png build/seals.png
python3 tools/sealshot.py build/_base_expanded.gb --seals 0,1,2,3   # the JP control
```

**The wording came from the item descriptions, not from scratch.** Bank 13's 122
descriptions cover the same effects at greater length and are already reviewed, so they
settle the terminology: `Deals heavy damage to Dragons` (13:$56C1), `To Ghost monsters`
(13:$5736), `To one-eyed foes` (13:$57E2) — which is why the one-eye seal is `One-Eyes` and
not "Cyclops", against `ひとつめゴロシ` = Cyclops Bane in the glossary — `Your attacks never
miss` (13:$5793), `Never rusts` (13:$58CD), `Reflects magic attacks` (13:$5993), `Cuts
damage from explosions` (13:$5A2C). **A seal and its own description must not read like two
different effects.**

* **The glossary does NOT bind these, and the old brief was wrong that it would.** `ドラゴン`,
  `ゴースト` and `ひとつめ` are not frozen names — the frozen ones are the compounds
  (`ドラゴンキラー`, `ひとつめゴロシ`). `lint_en` reports 0 problems either way. What binds
  the terminology is the reviewed description text above.
* **Byte budgets were never the constraint.** All 20 fit in place after the repack; bank 11
  closed at `+9 spare` on 4107 bytes and nothing needed a redirect.

The old "~110 strings" counted the bank-13 and bank-3 false positives and some strings
session 4 has since done. The 12 remaining non-text entries need nothing.

### Session V1 — CLOSE THE TWO MEASURED MENU GAPS — **COMPLETED 2026-08-08**

Joey's screenshot sweep found two paths that the prior start-flow fixture did not cover.
These are ordinary pre-cinematic closure work, not visual polish:

1. **Rank/Pass popup:** box 45, shape `x3,y8,n2,w6,flags02`, stages `00 Rank FF` at
   `$C616` and `00 Pass FF` at `$C61C`. Its selector and allocator now guard the exact
   shape, per-row source, physical cap, and payload. Static-prefix mode preserves the
   cursor cell and paints into `$82-$85` / `$9A-$9D`.
2. **Erase confirmation:** selecting Log 2 first uses VWF box 26 (`2: Log of Shir` / `en`).
   After VWF box-28 `No/Yes` appears, box 27 redraws the same record one cell wider as
   `2: Log of Shire` / `n`. Dot `2`/`3` plus that extra `e` needs nine physical tiles;
   the old `$82-$89` row-0 allocation had eight, so only Log 1 composed. A direct
   title-flow census found zero outside-row references to `$8A` in all three confirmation
   contexts, while nearby `$96-$99` were live; row 0 now safely uses `$82-$8A`.

`tools/startspill.py` drives all three erase logs and the real Rank/Pass route and now also
rejects static tile IDs referenced by any unowned settled screen cell. Normal and shuffled
builds each pass **46 title + 3 selector + 27 summary + 6 confirmation + 2 Rank/Pass calls,
84 epilogue-exact rows, 16,182 visible checks, zero problems**. Screenshots are under
`build/startspill_v1*/`. Both layouts also passed `menuromspill`, `rankspill`,
`newgamesmoke`, every `menuspill` mode, and 12 dungeon + 12 town crash seeds.

### Session 11 — THE PROLOGUE/ENDING CINEMATIC — **COMPLETE; VISUALLY APPROVED 2026-08-09**

The authoritative implementation/evidence is the current block at the top of this file,
`tools/intro.py`, `script/intro.tsv`, `tools/introspill.py`, and
`tools/introplayback.py`. The remainder of this
session section is the historical research brief. Its `$5C63-$5FA0` boundary, incomplete
arity warning, 77-byte alphabet-patch proposal, and “next” language were superseded by the
measured relocation/static-pack implementation; do not implement them.

**Joey booted the ROM, pressed nothing, and the opening story played in Japanese.** Every
check in §1 was green, `coverage.py` reported zero unextracted dialogue, and §2 said the
script was finished. All of that was true and none of it was about this text.

#### It is a bytecode VM with its own character table, and that is why nothing saw it

```
31:$5C63 - $5FA0   the program: ~830 bytes, 7 scenes (the <4D><C8> scene-end opcode
                   occurs 7 times and ALL SEVEN are in this range -- there is exactly
                   one program of this kind in the ROM)
13:$7FAA           the character table: 77 entries, intro byte -> font code
```

**The table is the whole discovery.** It is the game's character inventory, densely packed:

```
$00        space
$01-$2E    あ .. ん          (46, contiguous -> font codes $0B-$38)
$2F-$31    っ ゃ ょ
$32-$42    イウオキケコサシタニハフヤラリンッ   the 17 katakana the game owns
$43-$44    ！ ？
$45-$46    ゙ ゚               THE DAKUTEN PAIR
$47-$4B    「 」 ・ 、 。
```

So `あ` is `$01`, not `codec.py`'s `$0B`. Read through `codec` the cinematic decodes as
fluent-looking nonsense — `おさなごを` comes out `ぇうくおを` — which scores *well* on every
"is this text" heuristic the extractor has. **It was never rejected; it was never asked
about.** `regions.py` (session 7) and `impossible()` (session 8b) were both one table
applied where a second was needed. This is the third, and the first one where the second
table is a real ROM object you can point at rather than a stale copy.

> **`coverage.py` CANNOT be blamed and MUST be fixed.** Its contract is "is what we
> extracted all there is", and it answers it by decoding through `codec`. A run in a third
> encoding is invisible to it *by construction*, not by an oversight in its thresholds.
> Extending it means giving it the second table and re-running its classifier under both —
> and the honest lesson is that a coverage check is only as complete as its alphabet.
> **Do this before believing "the script is finished" a second time.**

#### The combining marks PRECEDE the kana here — the opposite of the main script

`むら ゙ ひ と` is むらびと; `かわいそう ゙た ゙か` is かわいそうだが; `コッ ゚ハ` is コッパ.
[[shiren-gb-text-encoding]] records "dakuten follows the kana", which is true of the main
script and **false here**. The renderer draws the mark into the tilemap row ABOVE the text
row, so a line occupies two rows and the mark lands over the character that follows it.

#### What the cinematic says (decoded 2026-08-06; 29 text runs, 12 reviewable lines)

```
ははおや「わたしの おさなごが・・・」
むらびと「かわいそうだが シキタリだ。  あきらめるしかねえ・・・」
ははおや「ああっ どうして・・・」
ここ すうねんまえから・・・
おさなごを かいぶつの  いけにえにささげているという
ひとつの ちいさなむらが あった
コッパ「ふうっ、」「やっと でられたな。」
「ほら、あそこ！」「ササラやまが みえる！」
「ここまでくりゃ もう にどと  もどされることも ないとおもうぜ」
コッパ「ケヤキちゃんのことか？」「けなげで いいごだったよな・・・」
コッパ「しょうがないよ。」「オイラたち フウライニンだもンな。」
「さ、」「いこうぜ！」
```

#### THE BLOCKER, and it is small and made of data

**The table cannot spell English.** Its 46 contiguous entries reach font codes `$0B`-`$38`,
which after `latinfont.py` is `A`-`Z` and `a`-`t`. **There is no `u`, `v`, `w`, `x` or `y`,
and no `.` or `-`.** (`$2F`-`$31` happen to give `'`, `z` and `,`.)

**The fix is 77 bytes of data, not code.** Once the cinematic is English its 17 katakana
slots (`$32`-`$42`) are dead, which is five more than the five letters needed. Repoint
those entries at font codes `$39`-`$3D` (`u v w x y`) and `$3F`/`$42` (`.` `-`) and the
alphabet is complete. `13:$7FAA` is untouched by the build today — verified byte-identical
between `_base_expanded.gb` and `shiren_en.gb` — so it is free to take a patch.

#### IS THERE AN ENDING CINEMATIC TOO? — asked by Joey, answered 2026-08-06

His worry was the right one: if one encoding hid a whole cinematic, a second could hide
the ending, and nobody would know until someone finished the game. **Three independent
checks say there is only this one program, and one of them does not depend on the
alphabet at all:**

1. **`tools/introsweep.py`** sweeps the whole ROM in the cinematic's alphabet, gated on
   punctuation the way `coverage.py` gates the main script. 319 runs pass; **exactly six
   read as sentences and all six are inside `31:$5D37`-`$5EF3`**, the program already
   known about. The rest is tile data that happens to decode.
2. **The scene-end opcode `<4D><C8>` occurs seven times in the ROM and all seven are
   inside `31:$5C63`-`$5FA0`.** One program of this kind, not two.
3. **`13:$7FAA` is the ROM's only character table** — and this is the check that does not
   care what alphabet a hypothetical third encoding uses. Every `ld hl,nn / add hl,bc|de /
   ld a,[hl]` site in the ROM gives 56 candidate lookups; scoring each for the long
   ascending run a character inventory must contain leaves exactly one. The nearest miss
   is `4:$79C4` — 32 entries, `and $1F`, five bits per character — and `4:$796F` feeds it
   from a **RAM** pointer table, so it decodes player data, not stored script.

**And Joey's own reading is the likeliest explanation anyway:** SNES Shiren delivers its
ending through the normal engine despite an elaborate opening, and this game does the
same — session 8 already translated the ending narration, which is ordinary bank-11/14
dialogue (`14:$6C3E`, "And there ends the talking to himself of a foolish man...").

> **A LEAD, NOT A FINDING, recorded so it is not lost:** `4:$796F` expands exactly **four**
> characters through that 32-kana table into `$C616`. Session 1b widened names from 4 to 6
> and never touched this path. It is not text so it is not session 11's problem, but it is
> the same shape as [[shiren-gb-layout-duplicated-in-code]] and worth ten minutes some day.

#### What is NOT established, and must be before a word is written

* **The opcodes — TWO of them are now measured, the rest are not.** `$4D` takes ONE
  argument byte and `$4E` takes **TWO**, established by drawing the line on the real
  screen and reconciling it against the bytes: the mother's line is
  `「わた <4E> 00 05 しのこ ゙か ・・・」` and the screen draws `「わたしのこが・・・」`, which only
  works if `4E 00 05` is one opcode. **Charging `$4E` one argument yields `わたおしのこが` —
  wrong, and reads almost right.** That is exactly the failure `<cF0:56>` hid a real
  character behind. `introlines.py` charges every other opcode zero, which lifts the text
  out cleanly (the whole program reads as fluent Japanese, which is the falsifier) and is
  **not** enough to write bytes back. Measure the rest in `gbemu.py` before inserting.
* **The line geometry.** Two tilemap rows per line (text + marks above), text seen at rows
  14 and 16, but the width and the line count per scene are unmeasured. The Japanese is
  the falsifier, the same as everywhere else.
* **The byte budget.** It is in bank 31, which is fragmented, and the program is bracketed
  by graphics on both sides. No redirect mechanism reaches it — `pool.py` works on
  `script.json` strings and this is not one.

**And the region is intact:** all 829 bytes are byte-identical between the Japanese and
English builds, so the repacker has never allocated into it. Confirm that again after any
change to bank 31's free-run map.

### Session 10 — graphics, and the FLOOR-NAME BANNER is the urgent one

**RETRACTED: "dungeon names are already strings and already handled" was wrong.** Joey
flagged it on 2026-08-04 and it does not survive a look. There is no dungeon-name string in
`script/script.json` at all — a sweep for マウンテン / どうくつ / ダンジョン / かいだん finds
item and monster names and one line of prose, and nothing that could be a dungeon title.

#### 1. The per-floor name banner — **COMPLETE 2026-08-10**

**A player sees this on EVERY floor of every dungeon.** It is by some distance the most
visible untranslated thing left in the game, and it is not text.

![the banner](build/floorname_banner.png)

What was established 2026-08-04, from `saves/floorname.state` (which `tools/mkstate.py`
now builds — it is a timed screen with no input, so a frame offset is the only handle):

* It draws `1 変化の森` — "Forest of Change", floor number then dungeon name — full-screen
  on a blank field, for **about 120 frames**, on arrival at a floor.
* It is **BG rows 8 and 9, tiles `$80`-`$A7`**, laid out as 20 column-pairs — a 160x16px
  strip, one tile column per screen column. `LCDC=$D5`: BG map `$9800`, tile data `$8000`
  **unsigned** (the composer's screens use `$8800` signed, so this is its own mode), window
  and sprites off.
* **Not one of those 40 tiles exists anywhere in the ROM.** Searched byte-for-byte over the
  whole 1 MiB. They are built at runtime — decompressed, or composed from a 16px font — and
  that is the fork the next session has to settle first.

**Update 2026-08-10 — the entire shared card path is established and implemented.** A deterministic
blank-cartridge New Log trace reaches the village card at frame 2260 with `LCDC=$D5`.
`31:$5FA9` enters the shared card path; `31:$60E1` clears all 40 tiles in five queued
128-byte batches, `31:$613E` maps `$80-$A7`, `31:$61C3` renders the numeric component, and
`31:$6241` renders the name. `DE+2 & $0E`, divided by two, is the eight-entry label
selector; `DE+1` is the displayed floor number and zero means a name-only card. The three
native village glyph uploads pass through `31:$62FF` to `$88E0/$8920/$8960`.

`tools/markers.py` replaces the name call at `31:$613A` for every selector. Ten static
one-bit bases cover the numberless and numbered forms of `Moonlight Village`, `Forest`,
`Koma Cave`, `Crags`, `Kuyo Pass`, `Dragon's Maw`, `Orochi`, and `Moon Exit`; a live digit
overlay keeps a fixed, right-aligned two-digit field through floor 50. The routine expands
each base into the native two-plane five-VBlank queue. Its code/data occupy bank 63
`$6DB0-$7C3C`, after the cinematic allocation; the local far-call stub is in the asserted
retired reader tail at `31:$51E0`.

The static table at `31:$6348` contains those eight name records in the same order as the
bank-11 place list. The normal 24-card selector progression at `31:$6370` is
`0,1,1,2,2,2,2,3,3,3,3,4,4,4,4,5,5,5,5,5,5,5,6,7`; the displayed-number table at
`31:$6358` makes the village, Dragon's Maw threshold and Moon Exit name-only on that path.
An alternate path can number Moon Exit, so the replacement retains that form as well.

`tools/markerspill.py` drives the real New Log route and requires all 640 village-card
bytes plus both tilemap rows to match exactly; `tools/newgamesmoke.py` proves the transition
still reaches a responsive village. `tools/floormarkerspill.py` walks from the supplied
town state into the real Forest 1F card, then exercises every stored card form and all ten
live digits through the same runtime hook. All 11 cases are exact.

**Style decision from Joey, 2026-08-10:** town and dungeon markers must keep one shared
16px-high graphic treatment, matching Shiren 1 SNES/DS; do not shrink dungeon labels to
an 8px variant. The existing compact place-table terms make that possible in the same 2x
Dot style even with floor 50: `Dragon's Maw` is the widest at 139/160px; `Koma Cave` 112,
`Kuyo Pass` 110 and `Moon Exit` 106. The full `Moonlight Village Exit` would be 204px, so
the already-established compact UI term `Moon Exit` is the required card spelling.

**Superseding artwork revision, 2026-08-11:** Joey supplied clean Poppins Medium mock-ups
for `Moonlight Village` and `1 Forest`; both now match pixel-for-pixel in the emulator.
The village's descenders make the approved raster 18px high, so `tools/markers.py` expands
the native banner to three visible rows (`$80-$BB`) plus four blank queue-pad tiles. The
native background fill now uses the explicit blank `$BC` tile, preventing `$80`'s first
letter pixels from repeating outside the banner. Eleven static bases and 50 live Poppins
number fields occupy guarded bank 60 `$5000-$747D`; the cinematic bank is no longer used.
`markerspill.py` requires all 1,024 VRAM bytes, all map rows and all three fade shades to
be clean. `floormarkerspill.py` runs 72 exact emulator cases covering every stored form,
all native floor/selector pairings and every floor value 1-50. Its 22 numbered native
cards must put number and name on one shared line and keep their visible outer-margin
imbalance to four pixels or less. Selector-specific number/name origins replace the old
independent vertical centering and reserved-box horizontal centering. The real floor-19
Dragon's Maw SRAM route paints x=7..152, and `dragonmawmarkerspill.py` makes those exact
7/7px margins permanent. The 2026-08-10 Thin Pixel implementation details above are
historical only; this paragraph is the current V5C contract.

**One thing was disproved on the way.** The repo's single graphics note — *"unverified:
bank 0 `$3ABD` is an RLE decompressor"* — does not hold up as stated. Hooked, it fires 60+
times during boot and its writes go to `$C0xx`, the VRAM transfer queue, not to VRAM tile
data. It is queue plumbing. **Do not start from that address.** Start by hooking writes to
`$8800`-`$8A80` in the ~200 frames before the banner appears and seeing who makes them.

#### 2. Title screen and credits

Genuinely untouched, and lower priority than the banner for the obvious reason: a player
sees the title once and the credits never.

All of this is independent of the translation sessions and can run in parallel whenever.

## 4. Budget policy — reset 2026-08-09; do not collapse four limits into one

The canonical register is `VWF_BUDGETS.md`. Dot Gothic text is constrained independently
by physical pixels, source staging, temporary tiles and runtime substitutions. A combat
line and its substituted value share 144px, but not every control token receives every
kind of name and the current composer also has a separate **30-source-glyph guard**.

`tools/dialogue_preview.py` retains these compatibility symbols:

```
NAME_CAP     = 14     legacy <var> reservation; runtime census open
ITEM_CAP     = 16     legacy <cE3> reservation; runtime census open
PLAYER_NAME  = 6      settled 2026-08-03: the ROM now accepts six
```

The first two are **not settled Dot budgets**. They were created by adding the uniform
VWF's six extra characters to old fixed-width decrees. `lint_en.py` now calls a crossing
`legacy_cap_unreviewed` and tells the translator not to shorten automatically;
`fontaudit.py` labels the associated line results legacy-reservation warnings. The six
character player-name contract is real.

`FIXED_WIDTH = 18` remains valid for Japanese self-test and the fixed-width control. The
production Dot composer owns 144px and now stages at most 30 glyphs, using the measured
split reveal map that avoids live `$C0FE/$C0FF`. The earlier global 24→26 experiment was
rejected before that safe implementation existed; it is historical evidence against
changing a source guard without also proving memory ownership, pixel clipping and pacing.
Widen any other source path pixel-aware and by measured scope.

The acceptance order is: preserve natural wording; measure the exact runtime variant; fix
a source/allocator limitation when pixels fit; reword or wrap only when the painted extent
genuinely exceeds the physical geometry. Do not derive a universal cap from either the
longest glossary entry or the tightest unrelated combat template.

### The speaker tag is not the name — ruled 2026-08-05

Six NPCs are frozen as role+name compounds because the **NPC name table** needs them:
`<var>` substitutes one into a combat line, and `Kinji attacked!` does not say who Kinji is.
But 99 of session 5's strings *attribute* a line to one of them, and there the compound is a
stage direction, not a name — `Builder Kinji: ` is 15 of 24 cells, so line 1 was full before
the sentence began. Joey ruled off two real screens (`build/speakertag_choice.png`):

| Japanese | glossary (name table) | prose tag |
|---|---|---|
| だいくのキンジ / だいくのマサ | Builder Kinji / Builder Masa | **Kinji: / Masa:** |
| むらおさ / かんぬし / ぱしりのゴン | Village Chief / Shrine Priest / Gon the Gofer | **Chief: / Priest: / Gon:** |
| フミのはは | ~~Fumi's Mother~~ → **Fumi's Mom** | **Fumi's Mom:** |

`フミのはは` has no personal name anywhere in the script, so the short form would have been
the generic "Mother". **The glossary was reworded instead** — `Fumi's Mom`, 11 cells, the
same in both places, no exception needed. That is the documented procedure: when the
glossary is wrong, change the glossary.

`lint_en.ATTRIBUTION` permits the short form **only in the opening position**, and requires
both halves — the Japanese opens with the name AND the English opens with `Short:`. A
mention later in the same string is still checked, which caught four strings during the
session. This is deliberately not `glossary_ok.tsv`: 99 entries would make that file the
silencer its own header warns against.

> **Renderer split remains real.** Item descriptions (`13:$7E49` → `$C616` → box 7) own
> four 144px rows and the Dot menu renderer accepts 21 source glyphs; the shared TSV stays
> at 18 for the fixed-width control. Menus use descriptor pixels and allocator runs, not
> the composer's source guard. See `VWF_BUDGETS.md` for the current matrix.

## 5. Honest labels

> **The label this document got wrong, and it is the one that matters.** From 2026-08-03 to
> 2026-08-05 the opening line read *"the engineering is DONE — everything left is
> translation"*, stated flat, with no hedge. Both halves were false: the composer had a
> latent rendering bug, and the script was ~8 KB short of the ROM. Neither was found by the
> battery; both were found by Joey playing. **A claim of DONE needs the same evidence
> standard as a number** — and "every check passes" is not that, when nothing checks
> coverage. See §1's hole and session 7.
>
> **Session 7 nearly repeated it in miniature, which is why it is worth recording.** The
> first `coverage.py` printed *"OK: no unextracted dialogue"* while the shop's opening line
> sat unextracted — the check was sound but its scan only looked at `$FF`-framed runs, so
> its clean bill of health covered less than it appeared to. It was caught by spot-checking
> the tool against the three offsets the previous session had NAMED as missing, rather than
> by trusting its summary line. **A new check's first green is the least trustworthy green
> there is; test it against a case you already know the answer to.**

* **Measured:** everything in §2, the space numbers, the token counts, the caps as they are
  currently set in code.
* **Estimated:** the number of sessions the prose takes. It depends on review throughput,
  which nobody has measured. Treat the session list as an ordering, not a schedule. One
  data point now exists and it is not a rate: session 4 put 341 formulaic strings through
  in one sitting, and the village prose is neither formulaic nor the same shape.
* ~~**Assumed:** that VWF's per-character advance really is ~6px in practice.~~ **Measured
  2026-08-03**: the pen is exactly 6px, a line holds exactly 24 characters, and it is
  photographed. The old estimate of 25 assumed a per-glyph width table, which was not
  built — see the caps note above.
* **Unverified:** bank 0 `$3ABD` as an RLE decompressor (graphics).
* **Believed on weak evidence, and now named as such:** 18 candidate pointer tables whose
  entries are all one or two distinct values (`6:$7083`, `11:$4B12`, `15:$61D9`, …). Two
  members of that class have already been proved false by the damage they did — `6:$472F`
  and `13:$57AB` — and one, `9:$6FCD`, is load-bearing for `11:$5848`. See the end of
  session 4.

## 6. Workflow

Agreed with Joey 2026-08-03: **there is no human translator.** Claude translates in-session,
batch by batch, and Joey reviews **rendered boxes** — not TSV rows. So the loop is:

```
translate a batch  ->  lint_en.py  ->  repair  ->  dialogue_preview.py  ->  Joey reviews
```

No export format is needed; translation reads `script/script.json` directly. The reason the
lint matters is that a model drops `<var>` — which encodes cleanly, inserts cleanly, passes
every reference check and crash seed, and then prints "The  attacked!" on screen. That is
the only failure in this pipeline with no other detector. Memory:
`shiren-gb-ai-translation-workflow`.
