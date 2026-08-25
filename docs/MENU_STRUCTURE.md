# Menu systems and regional-blanking ownership

**Status:** Engineering map plus checkpoint-1 screen redraw and both checkpoint-2
Item entry/exit directions, measured 2026-08-23. The dispatcher, box catalogue, memory map,
and fixture-backed routes below are established. Routes marked `outline` or `inferred`
still need a real button-driven trace before later regional work depends on them.
Checkpoints 1-3 are committed, regression-complete, and visually accepted. Leaving
any of pages 1-4 keeps the outgoing page live until Status replaces it. Direct
Status-to-Items entry/re-entry blanks only BG rows 0-15, preserves the bottom Window, and
commits empty box chrome before item text.

Checkpoint 3 is frozen at implementation commit `34a20ec` on 2026-08-25. Its accepted
scope includes the screen-15 Adventure cursor correction, complete one- and five-row
Items/Floor shape conversion, live standing-Floor exit and paging, atomic Item-body/page
indicator publication, and direct screen-2 Action B-cancel back to its exact carried-Item
or settled standing-Floor parent. The acceptance record below separates conclusions
proved by `mgbdis` from conclusions proved by frame-level runtime fixtures.

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
| Shared Action/Item transition state | `$C1B4-$C1B6` | Held-Action row count and packed Item state; during exact Item paging `$C1B4` is the four-slice tile-copy counter, `$C1B5` marks an Items/Floor header change after the final body row, and `$C1B6` is the page phase (`2` body, `4` replacement header, `3` redraw tail). The lifecycles are mutually exclusive |
| Standing-item Floor settlement | `$C1B7` | One only after screen 1 selector `$FF` has completed; authorizes its exact live Status pop, then clears |
| Held-Action page-edge snapshot | `$C1B8-$C1BE` | Seven exact cells saved before box 6 overwrites the Item page marker; consumed by B-cancel parent reconstruction |
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
The atomic screen-15 publisher finishes before the native cursor initializer at
`4:$4E2B`. The translation therefore pre-stages cursor tile `$81` at
`$C341 + 64*$C6A5`; `tools/startspill.py` checks both that shadow cell and the first
published `$9841 + 64*$C6A5` BG cell, rather than accepting only the later settled menu.

## In-dungeon Status menu system

The established root is screen 0:

```text
Status                                                     screen 0
|-- Items                                                  screen 1, paged
|   |-- standing-item Floor page                           screen 1, selector $FF; appended after carried pages
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

The complete global action-verb inventory is deliberately not declared from these traces:
Floor, Pot-content, shop, Gitan, trap, stair, and debug contexts stage different lists.
Checkpoint 3 uses the narrower, fully enumerated carried-Item plus settled standing-Floor
scope below.

## Checkpoint-3 exact scope: screen-1 Item/Floor Action overlay

Checkpoint 3 changes one screen-2 overlay lifecycle over two exact screen-1 parent forms:

```text
Status screen 0 -> Items screen 1 (page 1, 2, 3, or 4)
                -> Action screen 2 / box 6
                -> B cancel -> the identical Items page and selection

Status screen 0 -> Items screen 1 -> standing-item Floor selector $FF
                -> Action screen 2 / box 6 (`Take / Fire / Swap / Info` for Wood Arrow)
                -> B cancel -> the identical settled Floor page
```

This is not shorthand for every menu containing an action verb. The admission predicate
must prove the direct `0,1,2` stack, screen 2, either an ordinary held-inventory selection
below `$C6AA` or selector `$FF` with the independently proven Floor settlement latch, the
standard menu viewport, and no shop-price context.
Screen 16 calls the same `4:$4987` handler but has no established button-driven route; it
remains conservative until such a trace exists.

`mgbdis` confirms the native builder at `30:$7D3C-$7DD1`. Its pointer table at
`30:$7DD2` selects three separate 11-category verb tables: held inventory at `$7DE8`,
Floor at `$7E14`, and Pot contents at `$7E40`. Checkpoint 3 admits the held table and only
the settled standing-item screen-1 route into the Floor table. The
held suffix at `$7DD8` adds `Drop`, optional `Name`, and `Info`; the separate Floor suffix
at `$7DE0` adds `Swap` instead. Other Floor-table callers remain out of scope. An
exhaustive item-ID census of the held table establishes these visible box-6 variants:

| Held item/state | Item IDs | Box-6 rows |
|---|---|---|
| Weapon, Shield, or Bracer | `$00-$33` | `Equip / Toss / Drop / Info` |
| Equipped Weapon, Shield, Bracer | `$00-$33`, equipped | `Remove / Toss / Drop / Info` |
| Arrow | `$34-$36` | `Equip / Fire / Drop / Info` |
| Equipped Arrow | `$34-$36`, equipped | `Remove / Fire / Drop / Info` |
| Food or known Herb | `$37-$54` | `Eat / Toss / Drop / Info` |
| Known Scroll | `$55-$6F` | `Read / Toss / Drop / Info` |
| Known Staff | `$70-$7B` | `Wave / Toss / Drop / Info` |
| Put-style Pot | `$7C-$80,$82-$84,$86-$87` | `See / Put / Toss / Drop / Info` |
| Push-style Pot | `$81,$85,$88-$89` | `See / Push / Toss / Drop / Info` |
| Any identity-hidden Bracer, Herb, Scroll, Staff, or Pot | corresponding range | insert `Name` immediately before `Info` |

The ordinary picker therefore has four rows for most known items, five for a known Pot
or an identity-hidden non-Pot, and six for an identity-hidden Pot. Those heights and both
`Equip -> Remove` substitutions are part of checkpoint-3 acceptance, not optional edge
cases. The builder also emits `Toss / Drop / Name / Info` for rare IDs `$8A-$8E` and
`Toss / Drop / Info` for `$8F-$90`, but a genuine carried-item route has not established
those as checkpoint admission cases; forced records may enumerate output but cannot prove
screen ownership.

### What changes in checkpoint 3

- Opening screen 2 retains the native overlay publication. Its proportional verb rows use
  six private four-tile slices only after proving that neither visible parent layer refers
  to those tiles; no opening blank is needed and the Item page outside box 6 remains live.
- Moving the Action cursor from first to last row and back must not redraw or blank either
  parent or overlay.
- B-cancel regionally retires box 6 and reconstructs the exact covered cells from the same
  Item or standing-Floor page. It must restore the original page number/selector,
  selected row, page marker or Floor box edge, Item names, equipment markers, borders,
  and Window without a full-screen blank.
- The contract applies independently to pages 1, 2, 3, 4, and the settled `$FF` Floor
  parent. Passing on page 1 cannot authorize any other parent.

### What does not change in checkpoint 3

- Selecting `Eat`, `Read`, `Wave`, `Equip`, `Remove`, `Fire`, `Toss`, or `Drop` may replace
  the menu with gameplay/effect handling; its native transition remains authoritative.
- `Info` to screen 4 and back is checkpoint 4. `Name` to screen 9 is a separate ownership
  epoch. Selecting a Pot's `See`, `Put`, or `Push` and any following selector/content
  screen is deferred with the Pot lifecycle.
- Floor screen 20/box 39, Pot screens 12/13, shop-priced/`Tag` variants, ground popup
  screen 3, debug screens 27-29, and the untraced screen-16 alias retain their current
  full-map-safe paths.

### Implemented ownership transaction

The exact screen-2 row-0 gate requires state `$00`, current screen/depth `$02`, stack
`0,1,2`, a valid selector within a 1-20-item inventory or `$FF` with `$C1B7=$01`,
`$C6DE=$00`, and the standard LCD/scroll/Window configuration. It then scans visible BG
rows 0-15 and Window rows 0-1.
Any reference to `$C7-$DE` rejects the private path; this also rejects shop Item pages
structurally because their price rasters occupy `$D0-$DE`.

An admitted Action picker assigns verb row `r` the fixed four-tile slice
`$C7 + 4*r`, for `r=0..5`. Thus the largest six-row picker owns exactly `$C7-$DE` and
cannot exhaust or alias the 72-tile Item-page allocator. The opening draw, box chrome,
cursor writer, and final map publication remain native; the new work is lifetime proof
and disjoint raster allocation, not a replacement overlay renderer.

The Action admission hook snapshots the exact seven-cell Item page-marker/top edge from
shadow `$C36D-$C373` into translation-owned `$C1B8-$C1BE` and saves the retained Item
record count in `$C1B5`'s high three bits before box 6 publication. The low five bits hold
the carried selector or sentinel `$1F` for the settled Floor parent. The B handler at
`4:$5689` reaches the generic pop arithmetic with `HL=$5689`; the hook at
`4:$485A-$4861` preserves that arithmetic for every caller and arms state `$07` only for
this exact call site and admitted screen-2 stack. While that pre-pop proof is still live,
it reconstructs the covered parent in shadow: rows 1-2 are truly empty, the saved row 3
restores the complete page marker or Floor top edge, and retained Item VWF records restore
any name tails at x=13..18 plus the native right/bottom borders. For `$FF`, the first
separator is the Floor box bottom and all later covered rows are true blank field. It then
drains the VWF queue, enters a fresh VBlank, and copies that completed parent only to box
6's physical footprint:

```text
BG start $982D = (x=13, y=1)
width             7 cells, x=13..19
height            2 * verb_rows + 1
four rows         y=1..9
five rows         y=1..11
six rows          y=1..13
```

Once the parent is visible, the helper restores the retained Item-record count, row shape,
cursor limit/position/base, exact Item/Floor descriptor, and current screen state. Carry
returns to the patched bytes at
`4:$485D`, which jump directly to the existing pop epilogue at `4:$4878`. The generic
shadow clear, screen-0 Status reconstruction, screen-1 Item reconstruction, and final map
copy are therefore skipped only for this already-complete transaction. That replay was
the source of the roughly 40-frame input stall after the screen looked settled. The exact
route now returns from the B handler two frames after the press, and a post-release D-pad
press is accepted normally. If any proof or restore fails, carry remains clear and
execution falls through at `4:$4862` to the unchanged conservative native replay.

This direct return is safe because Action uses disjoint `$C7-$DE` rasters, its admission
preserves the Item VWF records, and the restorer makes both shadow and visible box-6 cells
match their Item/Floor parent before the jump. The page number or Floor selector, cursor,
borders, equipment markers, all cells outside the footprint, and the hardware Window
retain their existing owners.

ROM/WRAM ownership for this checkpoint is:

| Owner | Range / value | Responsibility |
|---|---|---|
| Bank 37, far `$05` | `$405A-$4104` | live-layer admission, collision scan, and Item/Floor page-edge save dispatch |
| Bank 61, far `$07/$09` | `$405A-$40EF` | private Action-row allocator plus register-transparent initial screen-15 cursor staging |
| Bank 62, far `$07` | `$405A-$4314` | exact box-6 Item/Floor parent and screen-1 machine-state restorer |
| Bank 60, far `$0D` | `$422E-$429E` | exact generic-pop proof and direct-return dispatch |
| `$C1B4` | four, five, or six | retained box-6 verb-row count; temporarily four per tile during an exact Item-page upload |
| `$C1B5` | `rrr ii iii` | retained Item record count in bits 7-5 plus selector in bits 4-0; `$1F` means the Floor parent |
| `$C1B6` | zero through four | zero idle, one private Action-pool admission, two live Item-page transaction, three completed Item page awaiting redraw tail, four replacement Item/Floor header pending |
| `$C1B7` | zero or one | completed standing-item Floor page; authorizes only its proven Status pop, paging shape change, or screen-2 Action parent |
| `$C1B8-$C1BE` | seven tile references | saved Item page-marker/top edge under box 6 |

`tools/actionmenuspill.py` boots the real four-page Dragon's Maw inventory independently
for five full-inventory paths: page-1 `Equip`, page-1 equipped `Remove`, page-2 hidden
Bracer with five rows, page-3 `Eat`, and page-4 hidden Pot with six rows. Four additional
exact short-page shapes cover one through four pages and retained record counts below
five. Every run moves the Action cursor first-to-last-to-first, B-cancels, then immediately
moves Down and Up on the returned Item page. It verifies the exact `0,1,2` admission, all
private tile bases and both bitplanes, one `HL=$5689` pop, one VBlank parent restore, no
post-B Status/Items replay, B-handler return within two observed frames, accepted D-pad
input within two observed frames, no blank/mixed/unowned footprint, an immutable Window,
the identical final Item page/selector and menu-machine state, and zero LCD-off or
all-white frames. `menuspill.py --long` independently forces 11-tile Item rows so the
covered nonempty VWF tail reconstruction is exercised.

`tools/flooractionspill.py` independently traverses all four carried pages to the settled
Wood Arrow Floor page, opens its real four-row `Take / Fire / Swap / Info` box, and
B-cancels. It requires one private-pool admission, one `HL=$5689` pop, one exact parent
restore ending in VBlank, no screen/row replay, the exact settled Floor map and machine
state at return, a two-frame B return, and acceptance of the first subsequent Left input
in one frame. LCDC bit 7 remains set and no sampled frame is all-white.

The complete `build.sh` battery passes with this controller in the final ROM. That
includes both Item-page cadences, synthesized one- through four-page inventories, direct
entry/exit, held Action-to-Info and Name entry, Floor/Info, Pot/Info and Pot Put, the
seven-row out-of-scope Pot picker, shop prices, debug menus, and all start-menu composites.
This is automated regression completion, not manual visual acceptance.

### Frozen manual visual acceptance paths

1. On each of Item pages 1, 2, 3, and 4, open one screen-2 picker, move its cursor to the
   last row and back, then press B. Confirm the surrounding Item page never disappears
   and the same page/selection returns.
2. Separately inspect a four-row known item, a four-row equipped item showing `Remove`, a
   five-row known Pot or identity-hidden non-Pot, and a six-row identity-hidden Pot.
3. For the Pot representatives, stop after B-cancel. Do not select `See`, `Put`, or `Push`
   when judging checkpoint 3; those descendants are deliberately unchanged.
4. Optionally select one gameplay-bound verb only to confirm its existing transition was
   not broken. A full-screen blank on that replacement path is not a checkpoint-3 defect.
5. From PUSH START, open the initial title menu and confirm its cursor is already beside
   Adventure before any D-pad input.
6. While standing on an item with four carried pages, page right from page 4 to the
   appended Floor page. Confirm there are no vertical borders below its single item box,
   then press B and confirm Status replaces it without a full-screen blank.

### Checkpoint-3 acceptance record

Checkpoint 3 was frozen on 2026-08-25 against implementation commit `34a20ec`. The full
`build.sh` battery passed, and manual playtest accepted paging, Start-sort, both directions
of the carried-Items/Floor boundary, live Floor-to-Status, the first title-menu cursor,
all scoped Action overlay heights, prompt B-cancel, and immediate post-cancel input.

`mgbdis` supplied control-flow facts, not visual timing. Most importantly, the Japanese
base-ROM handlers at `4:$7339` and `4:$7354` update `$C6AC` and immediately invoke the
stack redraw at `4:$483E`; neither handler reads visible page-indicator cells
`$986F-$9872`. That disproved the translation-added indicator veto responsible for rare
state-`$06` full-screen fallbacks. Disassembly also established the real `$FF` Floor
selector, screen/box dispatchers, the box-6 verb-table split, and the exact
`HL=$5689` Action pop call site used to narrow the direct return.

Runtime fixtures supplied the facts that code alone could not prove:

- `itempagespill.py` showed that removing the false veto exposed slow proportional
  composition rather than an ownership failure. Holding rows 0-3 unreferenced and
  committing all five Item bodies plus the page indicator at final row 4 changed the
  visible sequence to complete old page, complete regional blank, complete new page.
- Rapid-cadence and synthesized-inventory fixtures showed that ordinary carried-page
  paging could be fast, while the one-row Floor/five-row Items shape boundary had to stay
  serialized to prevent overlapping input and corrupted chrome.
- `actionmenuspill.py` showed that the visually complete Item parent remained input-locked
  because native B-cancel replayed unpublished Status and Items screens. Exact footprint
  reconstruction plus direct restoration of screen-1 state removed that replay and its
  roughly 40-frame stall.
- `flooractionspill.py` proved that the same direct return is safe for selector `$FF` only
  with the independent settlement latch: B returns in two observed frames, the following
  Left input is accepted in one, and no sampled frame disables the LCD or becomes white.

The reusable engineering lesson is to use static disassembly to establish native control
flow and state producers, then use frame-level fixtures to establish ownership lifetime,
publication order, VBlank timing, and responsiveness. Neither evidence source replaces
the other.

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
| `$07` | transient admitted screen-2 Action B parent/machine-state restore; cleared before direct return |
| `$10` | title/file composite transaction |
| `$11` | difficulty composite transaction |
| `$12` | proportional Rankings map-swap transaction |
| `$13` | Fay composite transaction |
| `$14` | native Rankings transaction |

`$C1B7` is a separate one-bit settlement proof, not another `$C1B3` mode. It is set only
after screen 1 completes selector `$FF`. It admits only the proven direct Status pop,
Items/Floor paging conversion, or screen-2 Action parent; Action B retains it because the
result is the same settled Floor page, while an actual page exit clears it. A stale or
partially built `$FF` page therefore cannot broaden any live path.

Screen-1 Left/Right and Start-sort redraws use the narrow regional transaction below.
Exact direct Status-to-Items entry and Items-to-Status pops use the two broader directions
described afterward. Pot pages, unexpected nonempty Item fallback, standalone screen-20
Floor/Info, and unknown
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
For the standing-item Floor page (`$C6AC=$FF`), the same transaction has a narrower final
shape: only item row 0 exists. Its blank commit retains row 0's `$BE` left border but
zeros the left borders of outgoing rows 1-4 along with their interiors. This prevents
the four permanent vertical remnants that result from treating a one-row page as a short
five-row Item list. The shape-specific commit also rebuilds the complete empty Floor
rectangle at rows 3-5 before its first text row. In the reverse direction, a completed
Floor latch plus the incoming carried selector commits the complete empty five-row Items
rectangle at rows 3-13 before page text. Right selects page 1; Left selects the last
carried page. Both shape directions also retire the shared header interior at
`$C321-$C324/$9821-$9824`; box 14/18 then composes `Items`/`Floor` while no visible map
cell refers to those private title tiles. The regional controller masks IE around the ROM's internally-`EI` far-call
trampoline so both conversions finish inside the VBlank that begins their publication.

### Locked and separately mutable cells

The neighboring and separately mutable cells follow these ownership rules:

| Region | Address/shape | Rule |
|---|---|---|
| Items/Floor header boxes 14/18 | x `0..5`, y `0..2` | Lock for ordinary Item-page changes. An Items/Floor shape change owns only the four middle-row interior cells x `1..4`; its border remains locked |
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
   bit 7. It bounds native item count `$C6AA` to one through twenty and drains `$C11A`
   before taking ownership. `mgbdis` shows that native Right/Left first commits `$C6AC`
   and then synchronously calls `4:$483E`; neither handler nor the redraw uses visible
   `$986F-$9872` as an input. Those four cells are rendered output and can legitimately
   still describe the outgoing page while the next redraw is already owned. The former
   exact-marker validation could therefore decline a valid redraw into state `$06`, whose
   legacy publisher disables the LCD. Admission now relies on the native screen, row,
   allocator-epoch, selector flow and item-count state instead. Initial entry remains
   excluded by the fresh-allocation state latch and is owned by the separate screen-1
   pre-clear gate; an unsupported row still retains the distinct state `$05` LCD-off
   safety fallback.
2. After the predecessor proof, the controller normally writes `$BE`
   to the five marker-coupled left borders and clears exactly the five status-marker cells
   and five 16-cell name interiors in shadow, then applies the same regional state to
   visible BG during VBlank. Interrupts are masked only across the VBlank rendezvous/copy
   so the native handler cannot consume the write window, and are restored immediately
   afterward. Selector `$FF` instead converts the complete five-row Items box to a
   complete empty one-row Floor box and structurally zeros rows 6-13. A completed Floor
   latch with an incoming carried selector performs the inverse conversion to a complete
   empty five-row Items box. The same VBlank zeros the four shared title references.
   These shape commits finish inside VBlank; state then becomes `$01`, and LCDC bit 7
   never changes.
3. The existing allocator resets its row records at the new row-0 epoch, but no reused
   tile pixels are published until the old visible name references are gone. In the exact
   transaction, each 16-byte glyph tile is copied from composition WRAM in four
   synchronized four-byte HBlank slices; if VBlank begins, the remaining four-byte slices
   continue immediately. Interrupts remain masked across this short direct transfer so
   the destination/source registers cannot be disturbed. Other shapes retain the native
   `$C11A` tile queue. Completed rows 0-3 remain unreferenced behind the regional blank.
   When row 4 is complete, all five rows' 18 owned map cells are copied from shadow to BG
   together in one VBlank. The border and marker therefore appear as one completed native
   pair and the body cannot cascade top-to-bottom. `key+2` (cursor) and `key+19` remain
   outside this publisher. Selector `$FF` uses the same helper for its one real row.
4. The native short-page representation has no `$FF`: it is an exact 19-byte all-zero
   field. Mode 3 recognizes only that representation and builds the empty shadow row for
   the final atomic body commit. Any other nonempty fallback sets state `$05`, disables the
   LCD during VBlank, and completes through the shared full-map publisher.
5. The native cursor writer retains its responsibility. On an Items/Floor shape change,
   the structural blank clears `$9882`; after native `4:$4E2B` rebuilds `$C382`, the
   shape tail commits that one cursor cell with the completed title and indicator. Native
   `4:$4EB4` does not build the page indicator until after the body and header, which
   previously left a visually complete incoming page carrying the outgoing green dot for
   several frames. The exact
   final-body-row transaction now derives the same one-through-four-page map from
   `$C6AA/$C6AC` and commits `$C36F-$C372` to `$986F-$9872` in the same VBlank that
   publishes the complete body. The later native builder and redraw-tail copy are
   idempotent confirmation writes. The last body row also changes phase `$C1B6` from two
   to four only for an Items/Floor shape change, which forces native box 14/18 to compose
   the proper replacement word instead of reusing the outgoing static title. Completion
   of the four-cell header changes the phase to three.
   The `$4D7A`
   range-selector gate then publishes only `$C36F-$C372` to `$986F-$9872` at a
   scan-safe point for an ordinary page. A marked shape change instead publishes the
   completed four title cells and indicator together during VBlank. Unknown callers receive the
   native range values and continue into the untouched `$44A2` publisher. States
   `$05/$06` still route to the full fallback publisher. No Action, Info, or replay path
   can enter through the regional gate.

ROM ownership is explicit:

| Bank 60 range | Far index | Responsibility |
|---:|---:|---|
| `$405A-$4084` | `$05` | shared 20x18 fallback publisher |
| `$4090-$422D` | `$07` | exact screen-1 regional controller |
| `$422E-$429E` | `$0D` | Item/Floor Action B-pop proof and direct-return dispatch |
| `$4300-$43EE` | `$09` | initial/Pot/fallback controller |
| `$43F0-$444E` | direct | atomic five-row Item / one-row Floor body publisher |
| `$4480-$45A5` | `$0F` | Item page/header/cursor fast return plus native range-selector continuation |
| `$45A6-$45CE` | direct | final-body-row Items/Floor shape-phase marker and indicator dispatch |
| `$45E0-$46B0` | direct through `$0F` | scan-safe Item glyph-tile publisher |
| `$46B1-$46FF` | direct | native-equivalent page-indicator builder and VBlank publisher |
| `$4700-$4FFF` | — | redirected text; allocator origin raised to protect the code arena |

Allowed visual body states are `complete old -> complete regional blank -> complete new`.
Rows whose old and new pixels are identical may visually collapse adjacent states, but
the sole final-row VBlank hook proves there is no intermediate body publication. No row
may regress from new to blank or old.

### Checkpoint acceptance and evidence

- LCDC bit 7 stays enabled for every scoped Left/Right and Start-sort frame.
- Every Item name row is exactly old, blank, or complete new content.
- Header, right borders, separator rows, Window/status panel, and unrelated BG cells
  remain byte-exact on ordinary pages. Shape changes admit only blank or complete
  `Items`/`Floor` title interiors. Each left-border/marker pair is exactly old, `$BE,$00`, or complete
  new content; `$83,$00` and `$85,$00` are forbidden remnants.
- Page marker and cursor change only at their documented commit points.
- No tile-data slot is repainted while any visible BG or Window cell refers to it.
- A row becomes visible only after all queued or scanline-sliced bytes for its referenced
  tiles have landed.
- Tests cover one-, two-, three-, and four-page inventories; short final pages; every
  Right/Left page boundary including wraparound; reversal after settle; and Start-sort.
- Sampling continues through the transition tail to catch delayed replay or publication.
- Existing Action, Info, Pot, shop-price, hidden-identity, and debug fixtures still pass;
  they are adjacent ownership regressions even though their transitions remain LCD-off.

`tools/itempagespill.py` exercises eight complete five-row draws plus the native one-row
standing-item Floor page over four unique carried pages. Its seven direction presses cross the equipped
page-1 boundary both ways, then drive both physical stages of last-page-to-page-1 wrap;
Start-sort supplies the final redraw. Direct initial entry now records zero LCD-off frames;
every scoped Left/Right or Start-sort transaction also records zero. For each redraw it hooks the controller
immediately before shadow blanking,
after shadow blanking, and after BG blanking, proving that all 85 marker/name targets are
zero, all five left borders are `$BE`, and the complement is unchanged. Every sampled
left-border/marker pair is old, `$BE,$00`, or complete new content in both directions
across the equipped page boundary. Every sampled name row resolves by tile reference and both
physical bitplanes to old, blank, or complete new content. It directly hooks the sole
row-4 VBlank body commit, proves the raw marker returns with its incoming name, and locks
unrelated visible BG cells and structural tiles `$81`, `$83-$85`, `$B8-$BF`, and
`$C5/$C6`, and rejects state `$05/$06` on a
scoped flip. The standing-Floor wrap additionally proves that selector `$FF`, followed by the
selector-zero/all-`$BC` page-1 transient, begins two regional transactions with no fallback.
The second build invocation uses a 20-frame cadence and a carried-page-only four-page cycle;
all seven redraws remain regional with no fallback or LCD-off frame. It also records input
latency: those redraws are visually complete in 11-13 frames and return from the handler
in 15-17 frames. The ordinary cadence measures 11-16 visual frames and 11-20 handler
frames for carried pages; VBlank alignment on the Floor-to-five-row-Items header/body
conversion raises the bounded handler maximum to 23 frames.
Unlike the two-frame direct Action cancel, a page flip must compose five new proportional
rows; these values are therefore the bounded rendering cost, not an invisible replay tail.

`tools/floorpagespill.py` uses the Wood Arrow save to traverse selectors
`0,5,10,15,$FF`. After settlement it requires the one ground-item box at rows 3-5 and
twenty zero cells in every shadow and BG row 6-15. Three independent boots then leave
Floor by B, Right, and Left. B requires the same nine live Status uploads; Right returns
to selector 0 and Left to selector 15. Both paging exits require a byte-exact empty
five-row rectangle before text, while Items-to-Floor requires a byte-exact empty one-row
rectangle. All three routes require zero regional/status fallbacks, zero LCD-off frames,
and zero all-white frames. A second build route schedules every next input one frame after
native `4:$4856` returns. It proves exact `Floor` and `Items` title pixels at settlement
and crosses all four carried pages plus both Floor exits at the earliest accepted cadence.

`tools/fusioncountspill.py` synthesizes the shortest one-, two-, three-, and four-page
inventories (1/6/11/16 items). It cycles Right through every page and wrap boundary, then
Left through every page and wrap boundary, then invokes Start-sort: 3/5/7/9 real redraws,
all matched by regional begins, with zero fallback or LCD-off frames. Each blank commit
occurs during VBlank, contains `$BE` in all five left borders, and contains zero in all
five marker cells and all 80 name cells.

The real trace now reports `OOOOO -> BBBBB -> NNNNN`; identical empty rows can display
`=` without weakening the direct single-commit proof. The Start-sort capture likewise
exposes the complete five-row regional blank followed by one complete return while the
screen chrome remains visible. Automated correction
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

The exit requirement is explicit: pressing B on carried page 1, 2, 3, or 4, or on the
settled standing-item Floor page after them, must not blank the screen. This route does
not need an Item-region blank. The outgoing page owns the display
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
| `$C6AC` | less than `$C6AA`, or `$FF` with `$C1B7=$01` | a real selected carried item, or the independently proven completed standing-item Floor page |
| `LCDC & $F8` | `$E0` | LCD on, signed BG tiles, Window configuration intact |
| `SCY/SCX` | `$00,$00` | ordinary menu viewport |
| `WY/WX` | `$80,$07` | persistent two-row status Window at the bottom |

Only that complete predicate selects the live exit. Any unknown LCD-on Status return uses
the retained LCD-off fallback. In particular, Name-to-Items stack reconstruction is not
silently admitted; after it settles, a later direct Items B pop can qualify normally.
The `$FF` branch consumes and clears `$C1B7` before returning; selector `$FF` alone is
never sufficient.

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

`tools/floorpagespill.py` independently covers the fifth-page form. Its Status-entry
snapshot requires selector `$FF`, latch `$01`, the exact `0,0,1` stale stack and standard
viewport. It observes the same nine VBlank uploads and verifies that the latch is zero
after the final Status screen, with no full-screen blank.

## Checkpoint-2 acceptance record

Checkpoint 2 was frozen on 2026-08-23 against implementation commit `3489572` after it
passed manual review and the complete regression battery. The accepted visual contract
is:

- Status-to-Items retains the bottom status Window, regionally clears only the replaceable
  BG, publishes both empty box perimeters, and then reveals completed Item text rows.
- Items-to-Status leaves pages 1-4 visible until completed Status fields replace them; no
  Item page may trigger a full-screen blank on this direct exit.
- Paging in either direction and Start-sort retain the checkpoint-1 five-row regional
  redraw, including short inventories and every wrap boundary.

Any later change to these routes must preserve the ownership predicates and fixture-backed
fallbacks documented above, then pass a new visual review. Later checkpoints must not
broaden this frozen scope implicitly.

The 2026-08-24 standing-item Floor correction extends the implementation beyond that
historical pages-1-4 acceptance record. Its automated and visual contracts are accepted
as part of the checkpoint-3 freeze at `34a20ec`.

## What is not safe to regionalize yet

- **Info and other Action opens/closes:** the screen-2 B-cancel described above is
  regionalized only over carried Items and the explicitly settled standing-item Floor
  parent. Screen-20 Floor/box-39, Pot, shop, screen 16, and Action-to-Info lifecycles
  retain their established full-map transactions.
- **Start/title composites:** log summaries, confirmation, difficulty, Rank/Pass, Fay, and
  Rankings borrow planes across several boxes. Their current atomic controller remains.
- **Map, Quit, Replay, and gameplay verbs:** these are replacement paths. Preserve their
  native blank/transition unless a separate visual defect is demonstrated.
- **Name entry:** it replaces the menu and restores native tile planes on return. It is a
  separate ownership epoch.
- **Forced context-dependent screens:** a forced screen can draw plausible garbage or
  run through invalid state. It cannot authorize a blanking mask.

## Remaining exploration and implementation worklist

1. Trace the exact checkpoint-4 Action-to-Info, Info-page, and Info-return control flow
   with `mgbdis` and real button-driven fixtures before choosing any regional mask.
2. Extend the direct Window reference-set audits used by `itemexitspill.py` and
   `itementryspill.py` to any future
   route that keeps the hardware Window enabled.
3. Capture complete dispatcher logs for New Log, Copy Log, Erase Log, Rename, Rank, Replay,
   and every staged action verb. Replace every `outline`/`inferred` edge before using it as
   an implementation boundary.

The implemented scope remains narrow: screen-1 paging/Start-sort owns an exact five-row
mask; direct Status-to-Items owns BG rows 0-15 while locking the Window; direct
Items-to-Status owns only nine private field uploads; and admitted screen-2 Action
B-cancel owns box 6 plus the exact Item/Floor input state needed for its direct return.
Native final-map
publication remains authoritative on every rebuilding route. Every direction retains the existing full-screen-safe path whenever an
allowlist or ownership assertion fails.
