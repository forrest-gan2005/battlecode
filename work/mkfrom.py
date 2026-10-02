import sys, os, glob
sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay
from collections import Counter
OUT = '/Users/quasarpark/meow-loop/tune_runs/sprintmaps'
os.makedirs(OUT, exist_ok=True)
for f in sys.argv[1:]:
    info, _, _ = replay.parse(f)
    lines = info['map'].splitlines()
    W, H = map(int, lines[0].split()[1:3])
    sym = [l.split()[1] for l in lines if l.startswith('SYMMETRY')][0]
    name = [l[9:] for l in lines if l.startswith('MAP_NAME')][0]
    spawns = Counter(); last = 0
    for ev in replay.load(f).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart': last = pl.i32(0)
        elif k == 'tileChange' and pl.u32(0) == 1: spawns[replay.point(pl.pointer(0))] += 1
    def mirror(x, y):
        if sym == 'xy': return (W - 1 - x, H - 1 - y)
        if sym == 'x': return (x, H - 1 - y)
        return (W - 1 - x, y)
    dur = max(last, 1)
    out = []
    for l in lines:
        q = l.split()
        if q and q[0] == 'TILE':
            x, y = int(q[1]), int(q[2]); n = spawns[(x, y)] + spawns[mirror(x, y)]
            if (x, y) == mirror(x, y): n *= 2
            if n == 0: out.append(f'TILE {x} {y} 0 0'); continue
            g = 2.0 * dur / n
            hi = max(1, int(round(2 * g - 1)))
            out.append(f'TILE {x} {y} 1 {hi}')
        else:
            out.append(l)
    fn = os.path.join(OUT, name.lower().replace(' ', '_') + '.map')
    open(fn, 'w').write('\n'.join(out) + '\n')
    print(fn, W, H, sym, 'rounds', dur, 'spawn tiles', len(spawns))
