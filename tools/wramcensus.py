#!/usr/bin/env python3
"""Which WRAM bytes does the game ever touch? Snapshot-diff over seeded play."""
import os, sys, random, argparse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, 'tools')
from gbrun import _import_pyboy, WALK_SEQ, PRESS_FRAMES

def census(rom, frames, state=None, seed=None):
    PyBoy=_import_pyboy()
    pb=PyBoy(rom, window='null'); pb.set_emulation_speed(0)
    if state:
        with open(state,'rb') as f: pb.load_state(f)
    else:
        for _ in range(400): pb.tick()
        pb.button('start', PRESS_FRAMES)
        for _ in range(200): pb.tick()
    base=bytes(pb.memory[0xC000:0xE000])
    touched=bytearray(0x2000)
    rng=random.Random(seed)
    n=0
    while n<frames:
        if seed is not None:
            pb.button(rng.choice(WALK_SEQ), PRESS_FRAMES)
        for _ in range(30):
            pb.tick(); n+=1
        cur=pb.memory[0xC000:0xE000]
        for i in range(0x2000):
            if cur[i]!=base[i]: touched[i]=1
    pb.stop(save=False)
    return touched

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('rom')
    ap.add_argument('--frames',type=int,default=3000)
    ap.add_argument('--seeds',type=int,default=6)
    a=ap.parse_args()
    total=bytearray(0x2000)
    runs=[(None,None)]
    for s in range(a.seeds):
        runs.append(('saves/dungeon.state', s))
        runs.append(('saves/town.state', s))
    for st,sd in runs:
        if st and not os.path.exists(st): continue
        t=census(a.rom, a.frames, st, sd)
        for i in range(0x2000):
            if t[i]: total[i]=1
        print('  %-22s seed %-4s -> %d bytes touched (cumulative %d)'
              %(st or 'cold boot', sd, sum(t), sum(total)), flush=True)
    # runs of untouched
    runs_out=[]; i=0
    while i<0x2000:
        if not total[i]:
            j=i
            while j<0x2000 and not total[j]: j+=1
            runs_out.append((0xC000+i, j-i)); i=j
        else: i+=1
    runs_out.sort(key=lambda r:-r[1])
    print('\nUNTOUCHED runs (top 25):')
    for a0,n in runs_out[:25]:
        print('   $%04X-$%04X  %5d bytes'%(a0,a0+n-1,n))
    open('/private/tmp/claude-501/-Users-joey-Documents-Workplace-Shiren-GB-1/80509d5e-f693-4e4e-a538-82df56e8a33a/scratchpad/wram_touched.bin','wb').write(bytes(total))
main()
