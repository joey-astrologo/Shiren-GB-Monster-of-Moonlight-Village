# Menu systems and regional-blanking ownership

**Status:** Engineering map plus checkpoint-1 screen redraw and both checkpoint-2
Item entry/exit directions, measured 2026-08-23. The dispatcher, box catalogue, memory map,
and fixture-backed routes below are established. Routes marked `outline` or `inferred`
still need a real button-driven trace before later regional work depends on them.
Checkpoint 1 (paging and Start-sort) is committed and visually accepted. Leaving any of
pages 1-4 keeps the outgoing page live until Status replaces it. Direct Status-to-Items
entry/re-entry now blanks only BG rows 0-15 and preserves the bottom Window; the entry
half commits empty box chrome before item text and awaits revised visual review.

This document answers two separate questions:

1. What screen or box is the game drawing, and what other menu content survives behind it?
2. Which visible tilemap cells and tile-data slots may be changed without corrupting that
   surviving content?

The second question is why this map exists. Japanese menu text refers to immutable glyph
tiles. English VWF rows refer to a small set of reusable tile-data slots. If an incoming
row repaints one of those slots while an outgoing visible cell still refers to it, the old
text changes underneath the player. The current translation prevents this by disabling
the LCD and rebuilding the whole 20x18 map. That is safe, but creates translation-only
full-screen white flashes.

Regional blanking is the intended replacement where ownership is provable: remove all
visible references in the region being replaced, then recycle its tile slots, render the
new pixels, and publish only complete rows. Native blanks used when entering gameplay,
Map, dialogue, or another genuinely new screen are not targets.

The load-bearing invariant is:

> Remove a tile's final visible BG or Window reference before repainting its pixels, and
> reveal a new reference only after those pixels are complete.

## Evidence and confidence

The static map was recovered from the matching base ROM with the sibling `../mgbdis`
checkout, then checked against the project disassembler and the built ROM. The base ROM
MD5 used for this pass is
`754398219a3ab38394cdac543d8deb47`.

Runtime routes were driven through the real dispatcher and drawers with the repository's
PyBoy fixtures. In this document:

- **measured** means a ROM address, table entry, or runtime value was observed directly;
- **fixture** means a real button-driven saved-state route reached it;
- **inferred** means the draw routine is known but its complete player-facing route has
  not yet been captured;
- **outline** preserves the navigation description supplied during planning and is a
  worklist, not yet an implementation fact.

For context-sensitive screens, forcing a dispatcher index is useful for discovering the
draw routine but is not route evidence. Several screens read selected-item, file, or
debug state and cannot be understood safely in isolation.

## The display model: there is no general menu z-buffer

Most menu boxes are composited into one 32-cell-stride WRAM shadow tilemap and later
published to the BG map. A later submenu appears to have a higher z value only because it
writes over cells drawn by its parents. The overwritten parent cells are not saved in a
separate layer.

The in-dungeon status panel uses the Game Boy Window and is a genuine separate hardware
layer. Its visible references count too: a BG tile cannot be recycled merely because no
BG cell refers to it if a visible Window cell still does.

| Purpose | Address | Ownership rule |
|---|---:|---|
| 20x18 menu shadow, stride 32 | `$C300-$C53F` span | Modify by exact visible cells; never clear the 12-byte row tails as map data |
| Visible BG map used by these menus | `$9800` base | Visible cell `(x,y)` is `$9800 + $20*y + x` |
| Corresponding shadow cell | `$C300` base | Shadow cell `(x,y)` is `$C300 + $20*y + x` |
| Alternate BG map | `$9C00` base | Translation title/Rankings code clears and uses it as a blank map; it is not a general free buffer |
| Menu upload scheduler | `$C006`, selector `$C11A` | Drain it before changing map ownership; do not bypass it with long LY busy-waits |
| VWF row scratch | `$C0CC-$C0DD` | Translation-owned while the menu renderer is active |
| VWF row records | `$C163-$C1B2` | Five-byte keyed records plus proportional metadata; ownership is per rendered row |
| Synchronous transition state | `$C1B3` | Translation-owned byte; values are listed below |
| Tile-12 composition buffer | `$C12C-$C13B` | Translation-owned scratch |
| WRAM-staged menu strings | usually `$C616-$C699` | The next draw can replace them; never treat the bytes as persistent row ownership |
| Active box descriptor | `$C69A-$C6A0` | Seven bytes: x, y, rows, width, flags, text pointer |
| Current screen ID | `$C6A3` | Also used by shared handlers to choose different boxes |
| Cursor home | `$C6A7/$C6A8` | Offset from `$C300`, loaded from the screen table at `4:$4E6E` |
| Dynamic row count | `$C6BB` | Used when descriptor flag bit 1 is set |

Tile IDs use LCDC's signed `$8800` tile-data selection. IDs below `$80` address
`$9000 + 16*id`; for example `$8B-$9D` wrap to `$88B0-$89D0`. A linear
`$9000 + 16*id` calculation for every ID would write into tilemap memory.

The shadow's address span includes 12 non-visible bytes after each 20-cell row. In the
last row that tail begins at `$C534` and is reused for the menu stack. The native clear at
`4:$480E` deliberately skips every tail. A “full shadow clear” must do the same.

### Dynamic tile budget

The proportional menu allocator has three useful contiguous runs:

| Run | Tiles | Capacity |
|---|---:|---:|
| `$43-$7B` | 57 | primary run |
| `$8B-$95` | 11 | one maximum-width Item row |
| `$9A-$9D` | 4 | short spill run |
| **Total** | **72** | fragmented, not interchangeable with 72 contiguous tiles |

Tile `$87` is isolated and cannot satisfy the minimum four-tile allocation, so it is not
part of the usable budget. English glyph tiles `$40,$41,$42,$7C,$7E,$7F` are reserved and
must never be allocated. Persistent Window tiles, including `$22,$24,$2A,$36`, must also
be excluded from any status-menu reuse set.

Measured residency gives the planning envelope:

| Scenario | Peak capacity owned |
|---|---:|
| Ordinary Status -> Items -> Action route | 32 tiles |
| Largest observed real save state | 50 tiles visible; 54 while building a fresh row |
| Synthetic five 11-tile rows plus four 4-tile action rows | 71 tiles |
| Full outgoing and incoming worst-case Item pages | about 110 tiles |

The last line rules out general double-buffering. It is the reason blanking the outgoing
Item references before recycling their tiles is the first design.

## Menu stack and redraw semantics

The menu stack is more important than the apparent visual hierarchy:

- `4:$47E8` initializes stack depth `$C534` to `$FF` and clears ten screen entries at
  `$C535` plus a second ten-byte region beginning at `$C53F`; the second region's exact
  semantics have not yet been named.
- `4:$4DDC` pushes a screen: it stores the ID in `$C6A3`, increments `$C534`, and stores
  the ID at `$C535 + depth`. A per-screen table at `4:$4E08` can initialize selection
  state.
- `4:$4857` removes a requested number of levels. It clears the visible 20 columns of
  all 18 rows in the **shadow** map, then calls `4:$487C`.
- `4:$487C` replays every surviving screen from stack entry zero through the new top.
  It sets `$C6A3` for each dispatcher call and keeps `$C6A6` nonzero during the replay.
- Only after the replay does the caller publish the reconstructed map through `4:$44A2`.

Consequences for regional blanking:

1. Pushing an overlay leaves its parent pixels and map cells live outside the child's
   rectangle.
2. Popping an overlay is not a local erase. The engine reconstructs every surviving
   screen into `$C300`; any retained native publisher can later expose that reconstruction.
3. A transaction is not complete when a desired screenshot first appears. It is complete
   when uploads and native publishers are drained and no replay can restore stale cells.
4. `$C6A3` names the routine currently being replayed, not necessarily the only logical
   screen visible to the player.

## Screen dispatcher catalogue

`4:$48AA` dispatches the screen ID in `a` through 35 little-endian pointers at
`4:$48C3`. “Box” refers to the descriptor catalogue in the next section.

| ID | Handler | Draw responsibility | Box(es) | Confidence |
|---:|---:|---|---|---|
| 0 | `4:$4909` | In-dungeon Status root | 0, 1, 2 | fixture |
| 1 | `4:$4980` | Interactive paged Items list; Items/Floor header selected by context | 4 and 14 or 18 | fixture |
| 2 | `4:$4987` | Inventory item Action picker | 6 | fixture |
| 3 | `4:$4999` | Ground-object confirmation/action popup | 3 | fixture: Trap, Exit, Stairs |
| 4 | `4:$49A7` | Item Info/description screen | 7 | fixture, including multi-page Info |
| 5 | `4:$49F5` | Equipment seals screen | 19 | measured; context-sensitive |
| 6 | `4:$4A4E` | No-items message | 9 | measured |
| 7 | `4:$4A58` | Floor header plus alternate Action picker | 5, 6 | measured/inferred context |
| 8 | `4:$4B02` | Name-entry variant with four-cell field | 10, 12 | fixture via file naming |
| 9 | `4:$4B20` | Name-entry variant with six-cell field | 11, 12 | fixture via Floor `Name` |
| 10 | `4:$4B3E` | No-more-names message | 16 | measured |
| 11 | `4:$4B44` | Item list plus `Which?`, or Floor fallback | 4 and 8, or 18 | measured/inferred route |
| 12 | `4:$4B81` | Pot contents/action list | 15, 17 | fixture |
| 13 | `4:$4BA2` | Alternate Pot contents viewer/selection behavior | 15, 17 | fixture: empty Pot `See` |
| 14 | `4:$4BEC` | Alternate Item list plus `Which?` | 4, 8 | measured/inferred route |
| 15 | `4:$4C15` | Title/start root choices | 23 | fixture |
| 16 | `4:$4987` | Alias of screen 2, inventory item Action picker | 6 | measured |
| 17 | `4:$4C23` | Fay's Puzzle task screen | 30, 31, 32 | fixture |
| 18 | `4:$4928` | Non-interactive Items redraw/helper | 4, 14 | measured/inferred role |
| 19 | `4:$4D72` | No passwords/awards fallback | 38 | fixture |
| 20 | `4:$4A58` | Real Floor item header plus Floor Action picker | 5, 39 | fixture |
| 21 | `4:$4C55` | Continue/New Game, or New Game only | 24 or 51 | fixture |
| 22 | `4:$4C61` | Log selector | 25 | fixture |
| 23 | `4:$4C75` | Save/log summary | 26 | fixture |
| 24 | `4:$4C94` | Confirmation text plus No/Yes | 27, 28 | fixture |
| 25 | `4:$4CAB` | Difficulty picker plus selected explanation | 29 and 46, 48, or 50 | fixture |
| 26 | `4:$4CCA` | Alternate wrapper/redraw of screen 22 | 25 | measured/inferred route |
| 27 | `4:$4CD0` | Hidden debug item-category picker | 33 or 34; optionally 37 | fixture |
| 28 | `4:$4CF8` | Hidden debug item picker | 35 | fixture |
| 29 | `4:$4D07` | Hidden debug enhancement/value editor | 36 | fixture |
| 30 | `4:$4D10` | Rank/Pass choice | 45 | fixture |
| 31 | `4:$4D20` | Rankings category choice | 47 | fixture |
| 32 | `4:$4D2B` | Pass log selector | 49 | fixture |
| 33 | `4:$4D39` | Rankings display | 41 | fixture |
| 34 | `4:$4D4A` | Password/award/clear-condition display | 42, 43, 44 | fixture |

IDs 2/16 and 7/20 share handler addresses deliberately. Screen 7 versus 20 is resolved
by checking `$C6A3`; the same code draws box 6 for 7 and box 39 for 20. A hook that keys
only on the handler address cannot distinguish those lifetimes.

## Box descriptor catalogue

`31:$4055` indexes 52 pointers at `31:$45D5`. Each pointer names a seven-byte descriptor
copied to `$C69A-$C6A0`. `31:$4075` draws the box into `$C300`; `31:$40D8` draws one row.
The descriptor width is the number of interior cells, so the left and right borders occupy
`x` and `x + width + 1`. Selectable list rows are commonly two tilemap rows apart; do not
derive a blanking mask from descriptor `rows` alone. Measure the physical row keys.

The catalogue below records the current English build. Several widths and high flag bits
differ deliberately from the base ROM.

Established native flag meanings are bit 1 = take row count from `$C6BB`, and bit 2 =
draw an extra separator before the bottom border. Higher bits are used by translation
rendering and must be interpreted through the current build, not the base drawer alone.

`WRAM` sources are volatile staging. A ROM-looking address below `$8000` is in bank 31
while the drawer is mapped unless its call site proves otherwise.

| Box | Descriptor | x,y | Rows | Width | Flags | Text source | Role |
|---:|---:|---:|---:|---:|---:|---:|---|
| 0 | `$41C2` | 0,0 | 3 | 5 | `$02` | `$C616` | Status choices |
| 1 | `$41C9` | 7,0 | 3 | 11 | `$44` | `$43B5` | Gitan / Floor / Path status |
| 2 | `$41E2` | 0,10 | 2 | 18 | `$04` | `$41E9` | Weapon/Strength and Shield/Experience |
| 3 | `$4205` | 3,4 | 2 | 6 | `$00` | `$C616` | Ground-object popup |
| 4 | `$420C` | 0,3 | 5 | 18 | `$02` | `$C616` | Items list |
| 5 | `$4213` | 0,0 | 1 | 18 | `$20` | `$C616` | Floor item header |
| 6 | `$421A` | 13,1 | 7 | 5 | `$02` | `$C616` | Inventory/alternate Action picker |
| 7 | `$4221` | 0,3 | 5 | 18 | `$00` | `$C616` | Item Info |
| 8 | `$4228` | 0,0 | 1 | 4 | `$70` | `$42CD` | `Which?` header |
| 9 | `$4235` | 0,6 | 1 | 18 | `$40` | `$423C` | No items held |
| 10 | `$424C` | 7,0 | 1 | 4 | `$04` | `$C6E3` | Short name field |
| 11 | `$4253` | 6,0 | 1 | 6 | `$04` | `$C6E3` | Long name field |
| 12 | `$425A` | 0,3 | 6 | 18 | `$04` | `$4261` | Name-entry keyboard |
| 13 | `$42D4` | 0,3 | 6 | 18 | `$04` | `$4261` | Alias keyboard descriptor |
| 14 | `$434F` | 0,0 | 1 | 4 | `$50` | `$422F` | Items header |
| 15 | `$435C` | 0,3 | 5 | 18 | `$02` | `$C616` | Pot contents list |
| 16 | `$4363` | 0,6 | 1 | 18 | `$40` | `$43DC` | No more names |
| 17 | `$437E` | 0,0 | 1 | 3 | `$60` | `$434C` | Pot header |
| 18 | `$4389` | 0,0 | 1 | 4 | `$50` | `$4356` | Floor header |
| 19 | `$4395` | 0,3 | 5 | 18 | `$00` | `$C616` | Equipment seals |
| 20 | `$439C` | 0,0 | 2 | 6 | `$00` | `$44BB` | Close/Quit |
| 21 | `$43AE` | 0,0 | 3 | 6 | `$00` | `$41D0` | Close/Exit/Quit |
| 22 | `$43C7` | 0,3 | 1 | 8 | `$00` | `$C616` | Context line/prompt |
| 23 | `$43CE` | 0,1 | 3 | 11 | `$02` | `$C616` | Title/start choices, dynamic 3-8 rows |
| 24 | `$43D5` | 3,4 | 2 | 10 | `$40` | `$436A` | Continue/New Game |
| 25 | `$43EF` | 5,9 | 3 | 9 | `$02` | `$C616` | Log selector |
| 26 | `$43F6` | 4,4 | 3 | 14 | `$04` | `$C616` | Save summaries |
| 27 | `$43FD` | 3,7 | 2 | 15 | `$00` | `$C616` | Confirmation prompt text |
| 28 | `$4404` | 11,2 | 2 | 4 | `$40` | `$440B` | No/Yes |
| 29 | `$4414` | 12,6 | 3 | 6 | `$50` | `$4453` | Difficulty choices |
| 30 | `$442E` | 0,0 | 1 | 18 | `$00` | `$441B` | Fay header/composite |
| 31 | `$4445` | 0,3 | 5 | 18 | `$04` | `$C616` | Fay tasks |
| 32 | `$444C` | 0,15 | 1 | 18 | `$40` | `$448F` | `Which task?` prompt |
| 33 | `$4467` | 0,0 | 5 | 6 | `$50` | `$432C` | Debug categories page 0 |
| 34 | `$4488` | 0,0 | 5 | 6 | `$50` | `$42E5` | Debug categories page 1 |
| 35 | `$44A6` | 4,0 | 4 | 14 | `$00` | `$C616` | Debug items |
| 36 | `$44AD` | 6,13 | 1 | 5 | `$00` | `$C616` | Debug value/enhancement |
| 37 | `$44B4` | 0,14 | 1 | 18 | `$00` | `$4435` | Pack full |
| 38 | `$44CA` | 3,9 | 1 | 13 | `$40` | `$43A3` | No awards/passwords |
| 39 | `$44E2` | 13,3 | 7 | 5 | `$02` | `$C616` | Real Floor Action picker |
| 40 | `$44E9` | 0,13 | 1 | 8 | `$00` | `$C616` | Context line/prompt |
| 41 | `$44F0` | 5,0 | 1 | 8 | `$40` | `$44D1` | Rankings header |
| 42 | `$4503` | 4,0 | 1 | 10 | `$00` | `$C616` | Password/award header |
| 43 | `$450A` | 7,3 | 1 | 4 | `$00` | `$C616` | Password field/short value |
| 44 | `$4511` | 0,6 | 5 | 18 | `$00` | `$C616` | Awards/clear conditions |
| 45 | `$4518` | 3,8 | 2 | 6 | `$02` | `$C616` | Rank/Pass |
| 46 | `$451F` | 0,13 | 2 | 18 | `$40` | `$4526` | Easy explanation |
| 47 | `$4542` | 5,7 | 2 | 10 | `$50` | `$446E` | Rankings category |
| 48 | `$4560` | 0,13 | 2 | 18 | `$40` | `$4567` | Normal explanation |
| 49 | `$4590` | 5,9 | 1 | 9 | `$02` | `$C616` | Pass log selector |
| 50 | `$4597` | 0,13 | 2 | 18 | `$40` | `$430B` | Hard explanation |
| 51 | `$45C3` | 3,4 | 1 | 10 | `$40` | `$449C` | New Game only |

## Transition ownership classes

Every route must be assigned one of these classes before a blanking implementation is
chosen:

| Class | What happens | Examples | Default policy |
|---|---|---|---|
| Page replacement | Same logical screen, same surrounding chrome, owned rows change | Items Left/Right; Info page change | Regional candidate |
| Overlay push | Child overwrites part of live parent; parent remains visible elsewhere | Item Action, confirmation, Rank/Pass | Blank only proven child/intersection cells; retain all parent owners |
| Stack pop/replay | Shadow is cleared and every surviving parent is redrawn | Info/Action cancel and many Back paths | High risk: intercept the final replay publication, not merely the top box |
| Composite redraw | Several boxes together form the apparent screen | Title plus log/difficulty windows; Fay; Rankings | Keep atomic policy until the full composite's owners and completion hook are known |
| Replacement screen | Menu is abandoned for Map, gameplay, dialogue, name entry, replay | Map, Quit, Take, Toss, Replay | Preserve native whole-screen transition; regional blanking has no benefit |

This classification supersedes the shorthand “higher z.” Two boxes can overlap in the
same BG map without being separate layers, while the status Window can be a separate layer
even when it looks like part of one screen.

## Start/title menu system

The player-facing outline is retained here, annotated with what has been tied to the
dispatcher. Indentation means a retained/composite parent unless a replacement is stated.

```text
Title/start root                                            screen 15
|-- Adventure
|   `-- saved-log summary                                  screen 23
|       `-- Continue / New Game                            screen 21
|           `-- gameplay/status                            replacement; screen 0 later
|-- New Log                                                outline
|   `-- log selection                                      screen 22 or 26
|       `-- difficulty + explanation                       screen 25
|           `-- name entry                                 replacement; screen 8 variant
|-- Copy Log                                               outline + fixture coverage
|   `-- source/target log selection                        screens 22/26
|-- Erase Log                                              outline + fixture coverage
|   `-- log selection
|       `-- prompt + No/Yes                                screen 24
|-- Rename                                                 outline + fixture coverage
|   `-- log selection
|       `-- name entry                                     replacement; screen 8 variant
|-- Rank/Pass                                              screen 30
|   |-- Rank category                                      screen 31
|   |   `-- Rankings                                       replacement/composite, screen 33
|   `-- Pass log selection                                 screen 32
|       `-- password/award/conditions                      replacement/composite, screen 34
|           `-- no-password fallback                      screen 19 when applicable
|-- Replay                                                 replacement into gameplay replay
|-- Fay's Puzzle                                           screen 17
|   `-- selected task enters gameplay/status               replacement; screen 0 later
```

Measured dispatcher sequences include:

- Adventure load: `15 -> 23 -> 21 -> 0`; moving among logs can redraw screen 23 more than
  once.
- Pass/award route: `15 -> 30 -> 32 -> 34`.
- Fay route: `15 -> 17 -> 0` after task selection.
- Copy, Erase, New, and name flows are exercised pixelwise by the current fixtures, but
  their complete dispatcher edge logs should be added before regional work targets them.

Title/file screens are composites. A child can borrow tile planes while title rows remain
visible, and returning can restore native planes. Current translation states `$10-$14`
protect these transactions; they are not candidates for the first regional checkpoint.

## In-dungeon Status menu system

The established root is screen 0:

```text
Status                                                     screen 0
|-- Items                                                  screen 1, paged
|   |-- Action                                             screen 2 or 16
|   |   |-- Info                                           screen 4, possibly paged
|   |   |-- Name                                           screen 9 in the measured route
|   |   |-- Pot contents / actions                         screens 12/13 by context
|   |   `-- gameplay dialogue/effect                       replacement by verb
|   `-- Left / Right                                       screen 1 regional redraw implemented
|-- Floor                                                  screen 20
|   |-- Action                                             box 39 within screen 20
|   |-- Info                                               screen 4, possibly paged
|   |-- Name                                               screen 9
|   |-- Swap                                               returns through Items/replay
|   `-- Take / Wave / Toss / Put / Push / etc.             replacement by verb
|-- Map                                                    replacement screen
`-- Quit                                                   replacement to gameplay dialogue

Other context routes
|-- ground Trap / Exit / Stairs confirmation               screen 3
|-- equipment seals                                        screen 5
|-- no-items/no-more-names                                 screens 6/10
|-- Which? selectors                                       screens 11/14
`-- hidden debug categories -> items -> value              screens 27 -> 28 -> 29
```

Representative real fixture sequences:

| Route | Dispatcher sequence | What it establishes |
|---|---|---|
| Status to Items/action/Info | `15,23,21,0,1,2,4` | Inventory Info is a child of paged Items and Action |
| Identity-hidden item | `...,0,1,1,2,4` or `...,0,1,1,1,2,4` | Screen 1 can redraw repeatedly before Action |
| Floor Info, two pages, Back | `...,0,20,4,4,0,20` | Info paging plus stack replay of Status and Floor |
| Gitan Info, Back | `...,0,20,4,0,20` | Three-choice Floor Action uses the same return lifecycle |
| Storage Pot Info, Back | `...,0,20,4,0,20` | Six-choice action geometry reaches the same lifecycle |
| Empty Pot `See` | `...,0,20,13` | Screen 13 is a real Pot viewer route |
| Ground Trap/Exit/Stairs | `...,0,3` | Screen 3 is the real two-choice ground popup |
| Hidden debug picker | `...,0,1,27,(27),28` then `29` | Debug screens are reachable from an Items context |

The action-verb inventory is deliberately not declared complete. Confirmed planning names
include Take, Wave, Toss, Swap, Name, Info, Put, and Push; equipment, food, scrolls, Pots,
Gitan, traps, and stairs stage different lists. Each verb must be classified by its actual
destination: overlay, replay, or replacement.

## Current transition controller

`$C1B3` is an English-only synchronous state byte. It must remain disjoint from dialogue
scratch and should remain nonzero until the associated pixels and map publication settle.

| Value | Current meaning |
|---:|---|
| `$00` | no translation-owned synchronous menu transaction |
| `$01` | screen-1 regional Item-page rebuild or direct Status-to-Items entry pending; also retained by legacy Pot handling |
| `$02` | Info construction/publication pending |
| `$03` | settled Info marker used to begin its return transaction |
| `$04` | Info-to-Action return pending |
| `$05` | regional Item attempt rejected after blanking; finish through whole-map fallback |
| `$06` | initial/declined Items entry latch; never reinterpret a later row-0 pass as Left/Right |
| `$10` | title/file composite transaction |
| `$11` | difficulty composite transaction |
| `$12` | proportional Rankings map-swap transaction |
| `$13` | Fay composite transaction |
| `$14` | native Rankings transaction |

Screen-1 Left/Right and Start-sort redraws use the narrow regional transaction below.
Exact direct Status-to-Items entry and Items-to-Status pops use the two broader directions
described afterward. Pot pages, unexpected nonempty Item fallback, Floor/Info, and unknown
LCD-on Status reconstructions still disable LCDC bit 7 before pixels are reused, build the
replacement in `$C300`, publish all visible 20x18 cells, then re-enable the LCD. That
retained path is the safe fallback. Regional publication changes scope and ownership
timing, not the text renderer itself.

## Item paging and Start-sort regional checkpoint

This is the narrow first-checkpoint implementation. It
covers same-screen page replacement and the Start-button sort redraw within screen 1: the
Items header, box borders, enabled bottom Window, and surrounding cells stay live. Action,
Info, entry/exit, and adjacent special routes do not inherit this five-row mask.

### Exact candidate mask

Box 4 is `(x=0, y=3, rows=5, width=18, flags=$02)`. Its five physical row keys are:

```text
row 0  $C380    row 1  $C3C0    row 2  $C400
row 3  $C440    row 4  $C480
```

Within each row, `key+0` is the marker-coupled left border, `key+1` is a raw
equipped/status cell, `key+2` is the cursor cell, `key+3..key+18` is the 16-cell name
interior, and `key+19` is the right border. An equipped `$84/$86` marker selects border
`$83/$85`; clearing only `key+1` leaves the border tile's vertical component visible.
The retirement state therefore normalizes `key+0` to `$BE` while blanking `key+1` and
`key+3..key+18`:

| Row | Shadow border / marker / name | Visible BG border / marker / name |
|---:|---:|---:|
| 0 | `$C380->$BE`, `$C381`, `$C383-$C392` | `$9880->$BE`, `$9881`, `$9883-$9892` |
| 1 | `$C3C0->$BE`, `$C3C1`, `$C3C3-$C3D2` | `$98C0->$BE`, `$98C1`, `$98C3-$98D2` |
| 2 | `$C400->$BE`, `$C401`, `$C403-$C412` | `$9900->$BE`, `$9901`, `$9903-$9912` |
| 3 | `$C440->$BE`, `$C441`, `$C443-$C452` | `$9940->$BE`, `$9941`, `$9943-$9952` |
| 4 | `$C480->$BE`, `$C481`, `$C483-$C492` | `$9980->$BE`, `$9981`, `$9983-$9992` |

This is a 90-cell write set: five normalized borders plus 85 blank marker/name cells. It
still retires at most 55 dynamic tile-data slots for five 11-tile proportional rows. The
border and marker tile planes remain immutable; only their map references change.

### Locked and separately mutable cells

The neighboring and separately mutable cells follow these ownership rules:

| Region | Address/shape | Rule |
|---|---|---|
| Items header box 14 | x `0..5`, y `0..2` | Lock map cells and every tile plane they reference |
| Item top border | y 3, x `0..19` | Lock except the page-indicator transaction below |
| Page indicator | shadow `$C36F-$C372`, BG `$986F-$9872` | Exclude from row clear; publish the new value at the explicit commit point |
| Equipped border/mark pair | each row `key+0..key+1` | Normalize to `$BE,$00`; republish the completed incoming `$83,$84`, `$85,$86`, or ordinary pair atomically; keep their tile planes immutable |
| Cursor | each row `key+2`; first is `$C382/$9882` | Exclude; hide/move at an explicit commit point, never through name-row blanking |
| Right borders | each row `key+19` | Lock |
| Inter-row separators and bottom border | rows between item keys and box bottom | Lock |
| Status Window | separate hardware layer | Lock its map references and tile planes for the whole transaction |
| Unrelated BG cells | complement of the exact masks above | Must remain byte-exact on every sampled frame |

“Locked map cell” also locks the referenced tile pixels. A tile ID shown in a locked cell
cannot be returned to the allocator even if its original VWF row record is being replaced.

### Implemented transaction

1. The row-0 upload hook calls bank 60 far index `$07`. It requires screen `$01`, VWF
   Item mode `$01`, shadow key `$C380`, bank `$C3`, a nonzero allocator epoch, and LCDC
   bit 7. It derives one through four pages from native item count `$C6AA`, matching
   `4:$4EB4`: one page leaves `$986F-$9872` as `$BC BC BC BC`; two through four pages
   contain exactly one active `$C6`, inactive `$C5` cells through the live span, and
   `$BC` in unused cells. The controller first drains `$C11A`, rendezvouses with VBlank
   again, and only then reads this visible marker. This ordering is
   load-bearing: validating first could sample a partially published marker, while
   reading immediately after a long drain could hit blocked mode-3 VRAM; either case can
   misroute a valid page change to the LCD-off fallback. These are phase-sensitive
   candidates consistent with the rare playtest report; the trigger itself has not been
   captured deterministically. The
   exact right-wrap transient also admits selector zero with
   all four cells `$BC`, after the native writer retires the old markers but before it
   draws page 1. Initial entry is owned by the separate screen-1 pre-clear gate below;
   unknown/declined entry remains latched as state `$06`.
2. After the predecessor proof, the controller writes `$BE`
   to the five marker-coupled left borders and clears exactly the five status-marker cells
   and five 16-cell name interiors in shadow, then applies the same regional state to
   visible BG during VBlank. Interrupts are masked only across the VBlank rendezvous/copy
   so the native handler cannot consume the write window, and are restored immediately
   afterward. State becomes `$01`; LCDC bit 7 never changes.
3. The existing allocator resets its row records at the new row-0 epoch, but no reused
   tile pixels are uploaded until the old visible name references are gone. Each renderer
   row completes its tile upload, then the controller drains `$C11A` again before copying
   `key+0..key+1` and `key+3..key+18` from shadow to BG. The border and marker therefore
   appear as one completed native pair. `key+2` (cursor) and `key+19` remain outside this
   publisher.
4. The native short-page representation has no `$FF`: it is an exact 19-byte all-zero
   field. Mode 3 recognizes only that representation, builds the empty shadow row, and
   publishes it regionally. Any other nonempty fallback sets state `$05`, disables the
   LCD during VBlank, and completes through the shared full-map publisher.
5. The native page indicator/cursor writers retain their responsibilities. Completion of
   the four-cell Items header clears a regional state `$01`; states `$05/$06` instead
   route to the full publisher. No Action, Info, or replay path can enter through the
   regional gate.

ROM ownership is explicit:

| Bank 60 range | Far index | Responsibility |
|---:|---:|---|
| `$405A-$4084` | `$05` | shared 20x18 fallback publisher |
| `$4090-$425E` | `$07` | exact screen-1 regional controller |
| `$4300-$43CF` | `$09` | initial/Pot/fallback controller |
| `$4400-$4FFF` | — | redirected text; allocator origin raised to protect the code arena |

Allowed visual row states are `old -> blank -> complete new`. A row may skip directly from
old to complete new only if non-aliasing is proven for every tile it uses. It may never
regress from new to blank or old.

### Checkpoint acceptance and evidence

- LCDC bit 7 stays enabled for every scoped Left/Right and Start-sort frame.
- Every Item name row is exactly old, blank, or complete new content.
- Header, right borders, separator rows, Window/status panel, and unrelated BG cells
  remain byte-exact. Each left-border/marker pair is exactly old, `$BE,$00`, or complete
  new content; `$83,$00` and `$85,$00` are forbidden remnants.
- Page marker and cursor change only at their documented commit points.
- No tile-data slot is repainted while any visible BG or Window cell refers to it.
- A row becomes visible only after all queued bytes for its referenced tiles have landed.
- Tests cover one-, two-, three-, and four-page inventories; short final pages; every
  Right/Left page boundary including wraparound; reversal after settle; and Start-sort.
- Sampling continues through the transition tail to catch delayed replay or publication.
- Existing Action, Info, Pot, shop-price, hidden-identity, and debug fixtures still pass;
  they are adjacent ownership regressions even though their transitions remain LCD-off.

`tools/itempagespill.py` exercises eight complete five-row draws plus the native one-row
right-wrap sentinel over four unique pages. Its seven direction presses cross the equipped
page-1 boundary both ways, then drive both physical stages of last-page-to-page-1 wrap;
Start-sort supplies the final redraw. Direct initial entry now records zero LCD-off frames;
every scoped Left/Right or Start-sort transaction also records zero. For each redraw it hooks the controller
immediately before shadow blanking,
after shadow blanking, and after BG blanking, proving that all 85 marker/name targets are
zero, all five left borders are `$BE`, and the complement is unchanged. Every sampled
left-border/marker pair is old, `$BE,$00`, or complete new content in both directions
across the equipped page boundary. Every sampled name row resolves by tile reference and both
physical bitplanes to old, blank, an in-VBlank blank-to-new publication, or complete new
content. It also proves the raw marker is blank with its outgoing name and returns in the
same commit as its incoming row, while locking unrelated visible BG cells and structural
tiles `$81`, `$83-$85`, `$B8-$BF`, and `$C5/$C6`, and rejects state `$05/$06` on a
scoped flip. The wrap sentinel additionally proves that selector `$FF`, followed by the
selector-zero/all-`$BC` page-1 transient, begins two regional transactions with no fallback.
The second build invocation uses a 20-frame cadence and a non-sentinel four-page cycle;
all seven redraws remain regional with no fallback or LCD-off frame.

`tools/fusioncountspill.py` synthesizes the shortest one-, two-, three-, and four-page
inventories (1/6/11/16 items). It cycles Right through every page and wrap boundary, then
Left through every page and wrap boundary, then invokes Start-sort: 3/5/7/9 real redraws,
all matched by regional begins, with zero fallback or LCD-off frames. Each blank commit
occurs during VBlank, contains `$BE` in all five left borders, and contains zero in all
five marker cells and all 80 name cells.

The real trace settles in top-to-bottom order. `tools/menuspill.py --ram` independently
reports `OOOOO -> BBBBB -> NBBBB -> ... -> NNNNN` and retains plane-exact allocator
ownership. The Start-sort capture likewise exposes the accepted complete five-row regional
blank and progressive return while the screen chrome remains visible. Automated correction
coverage also forbids the observed `$83,$00`/`$85,$00` vertical remnants. Checkpoint 1 is
the committed and visually accepted paging/Start-sort POC.

## Status-to-Items regional entry (checkpoint 2, entry direction)

Status and Items share the persistent hardware Window but replace essentially the whole
BG above it. A five-row Item mask is therefore insufficient on entry: Status VWF references
also survive in the header, menu choices, and value fields. The safe entry region is all
20 visible BG columns in rows 0-15. Rows 16-17 are covered by the Window at `WY=$80` and
remain locked together with the complete Window map and all planes it references.

The sibling `mgbdis` disassembly identifies the earliest safe screen-1 boundary:

```text
4:$494E  push af / push bc / push hl
4:$4951  ld hl,$C300
4:$4954  call $480E          ; clear 20x18 shadow cells, skipping stride tails
4:$4957  ld hl,$C549         ; item count/selector preparation follows
```

`statusvwf` replaces the six bytes at `$4951-$4956` with bank 53 far index `$09`. The
helper preserves the native shadow-clear result exactly and admits a live entry only with
this complete predecessor proof:

| State | Required value | Meaning |
|---|---:|---|
| `$C534` | `$01` | stack contains Status root plus the new Items child |
| `$C535/$C536` | `$00,$01` | exact root/Items screen IDs |
| `$C6A3/$C6A6` | `$01,$00` | direct screen-1 draw, not replay |
| `$C1B3` | `$00` | no other translation transaction owns the screen |
| `$C6AA` | `$01-$14` | one through twenty real items |
| `$C6AC` | less than `$C6AA` | valid retained selector before native reset |
| `LCDC & $F8` | `$E0` | LCD and Window enabled with signed BG tiles |
| `SCY/SCX` | `$00,$00` | ordinary menu viewport |
| `WY/WX` | `$80,$07` | persistent bottom Window |
| BG `$986F-$9872` | four `$00` cells after queue drain | exact Status predecessor, not a same-stack Item-page redraw |

The helper first drains `$C11A` and reacquires VBlank before reading the four predecessor
cells. It then clears four 20-cell BG rows per complete VBlank,
for four batches covering visible columns 0-19 in BG rows 0-15. Row tails, hidden BG rows
16-17, the `$9C00` Window map, and every tile plane stay byte-exact. Interrupts are masked
only while a batch is copied and are restored between VBlanks; all four measured batches
finish at LY `$94`.

The native order after this boundary is box 4's five Item rows, then box 14's `Items`
header, and only then `$4620` full-map publication. Publishing completed rows immediately
therefore produced the visually inverted sequence `text -> boxes`. At the end of the
fourth entry VBlank, the helper now commits the static box-14 header perimeter and complete
box-4 list perimeter while leaving both text interiors blank. The chrome commit finishes
inside VBlank and changes no tile plane. Item rows then appear progressively inside the
established list box; the native final publisher adds `Items`, the page indicator, and the
exact completed map. The visible order is now `regional clear -> empty boxes -> complete
text rows -> final decoration`, never text floating on an unframed field.

After retirement and chrome publication, state `$01` authorizes the existing completed
Item-row publisher. The helper performs the native 20x18 stride-aware shadow clear, each
Item row appears only after its VWF upload completes, and native `$4620` remains the final
map authority. Unknown callers receive only the original shadow clear and later fall
through to the conservative path.

`tools/itementryspill.py` independently starts from pages 1, 2, 3, and 4, exits to Status,
reopens Items, and immediately pages right. Each run requires one accepted entry, four
LY-`$94` blank batches, an exact chrome-first BG map completed inside VBlank before the
first Item-row call, an unchanged Window and tile planes, zero LCD-off/all-white frames,
and exactly one following five-row regional transaction with zero fallback. This covers
re-entry after every prior page-selector lifetime, not only the first opening.

## Items-to-Status live exit (checkpoint 2, exit direction)

The exit requirement is explicit: pressing B on page 1, 2, 3, or 4 must not blank the
screen. This route does not need an Item-region blank. The outgoing page owns the display
until the native Status publisher progressively replaces its cells with completed Status
content.

The native B handler at `4:$5689` reaches the generic pop call at `4:$568C`, reconstructs
screen 0, and invokes the Status field boundary at `4:$4FDD`. At that boundary the exact
direct predecessor is:

| State | Required value | Meaning |
|---|---:|---|
| `$C534` | `$00` | stack depth after the Items child was popped |
| `$C535/$C536` | `$00,$01` | surviving Status root plus stale popped Items entry |
| `$C6A3` | `$00` | Status is the screen currently being reconstructed |
| `$C6AA` | `$01-$14` | one through twenty items, hence at most four pages |
| `$C6AC` | less than `$C6AA` | a real selected item on any page, not a sentinel |
| `LCDC & $F8` | `$E0` | LCD on, signed BG tiles, Window configuration intact |
| `SCY/SCX` | `$00,$00` | ordinary menu viewport |
| `WY/WX` | `$80,$07` | persistent two-row status Window at the bottom |

Only that complete predicate selects the live exit. Any unknown LCD-on Status return uses
the retained LCD-off fallback. In particular, Name-to-Items stack reconstruction is not
silently admitted; after it settles, a later direct Items B pop can qualify normally.

The outgoing visible BG and Window reference none of the 40 private Status field IDs or
the eight structured Weapon/Shield IDs. Those 48 tile planes may therefore be restored
without changing a displayed Item pixel. `statusvwf` composes nine fields—Strength,
Experience, and seven values—then uploads each completed slice in its own VBlank. The
largest slice is seven tiles/112 physical bytes. Every copy starts at LY `$90`; observed
completion is LY `$92-$97`, inside the ten-line VBlank. Weapon and Shield retain their
source-stable four-tile fragments and need only their map references restored.

The VBlank rendezvous deliberately rejects a late VBlank tail. A real page-2 phase showed
that a native interrupt can begin just before `DI` and return at LY `$97`; treating that
as a fresh budget pushed the first upload through line 3. The controller now masks at the
end of visible scanout, rechecks LY, waits through the next visible frame if it arrived
late, and establishes BC/DE/HL only after interrupts are masked. Thus an interrupt cannot
corrupt either the byte count or VRAM destination.

`tools/itemexitspill.py` boots the real 18-item save four times and independently leaves
selectors 0, 5, 10, and 15. For every page it requires the exact stack/hardware predicate,
nine cap-ordered uploads `(6,7,5,2,4,4,4,4,4)`, starts at LY `$90`, completion no later
than LY `$99`, zero LCD-off frames, and zero all-white frames. At every sampled frame each
visible BG cell resolves to either its outgoing Item raster or final Status raster and
never regresses; the enabled Window map and all of its referenced planes remain exact.
All four routes settle to the same visible Status raster. The unidentified-item Name
fixture separately proves one conservative Name reconstruction followed by one live
direct Items exit.

## What is not safe to regionalize yet

- **Action and Info opens/closes:** their boxes overlap Item/Floor content and Back invokes
  replay. Existing `$02-$04` full-map transactions remain the baseline.
- **Start/title composites:** log summaries, confirmation, difficulty, Rank/Pass, Fay, and
  Rankings borrow planes across several boxes. Their current atomic controller remains.
- **Map, Quit, Replay, and gameplay verbs:** these are replacement paths. Preserve their
  native blank/transition unless a separate visual defect is demonstrated.
- **Name entry:** it replaces the menu and restores native tile planes on return. It is a
  separate ownership epoch.
- **Forced context-dependent screens:** a forced screen can draw plausible garbage or
  run through invalid state. It cannot authorize a blanking mask.

## Remaining exploration and implementation worklist

1. Stop for visual review of the revised Status-to-Items sequence: regional clear, empty
   boxes, then completed text rows. The automated ownership/order proof is complete, but
   its full-redraw appearance is a product decision.
2. Extend the direct Window reference-set audits used by `itemexitspill.py` and
   `itementryspill.py` to any future
   route that keeps the hardware Window enabled.
3. Capture complete dispatcher logs for New Log, Copy Log, Erase Log, Rename, Rank, Replay,
   and every staged action verb. Replace every `outline`/`inferred` edge before using it as
   an implementation boundary.

The implemented scope remains narrow: screen-1 paging/Start-sort owns an exact five-row
mask; direct Status-to-Items owns BG rows 0-15 while locking the Window; and direct
Items-to-Status owns only nine private field uploads while leaving native map publication
authoritative. Every direction retains the existing full-screen-safe path whenever an
allowlist or ownership assertion fails.
