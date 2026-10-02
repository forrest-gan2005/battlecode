import sys, os
sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay, bc
from collections import defaultdict
def estimate(f):
    info, _, _ = replay.parse(f)
    lines = info['map'].splitlines()
    W, H = map(int, lines[0].split()[1:3])
    sym = [l.split()[1] for l in lines if l.startswith('SYMMETRY')][0]
    name = [l[9:] for l in lines if l.startswith('MAP_NAME')][0]
    def mirror(p):
        x, y = p
        if sym == 'xy': return (W - 1 - x, H - 1 - y)
        if sym == 'x': return (x, H - 1 - y)
        return (W - 1 - x, y)
    corpse = set(); eats = defaultdict(list)
    _, evs, _ = bc.walk(f)
    for e in evs:
        if e[0] == 'death':
            for c in e[4]: corpse.add((e[1], c))
    present = set(); rnd = 0; last = 0; waits = defaultdict(list); empty_since = {}
    seq = []
    for ev in replay.load(f).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart': rnd = pl.i32(0); last = rnd
        elif k == 'tileChange' and pl.u32(0) == 1:
            c = replay.point(pl.pointer(0))
            if (rnd, c) in corpse or (rnd - 1, c) in corpse:
                present.add(c); continue
            if c not in present:
                waits[c].append(rnd - empty_since.get(c, 0))
            present.add(c)
        elif k == 'dragonUpdate':
            h = replay.point(pl.pointer(0))
            if h in present:
                present.discard(h); empty_since[h] = rnd
    est = {}
    for p in set(waits) | {mirror(q) for q in waits}:
        key = min(p, mirror(p))
        if key in est: continue
        w = waits.get(p, []) + (waits.get(mirror(p), []) if mirror(p) != p else [])
        if not w: continue
        if max(w) <= 1 and len(w) >= 2: est[key] = (1, 1); continue
        hi = max(w) if len(w) >= 3 else 2 * max(w)
        est[key] = (1, max(2, min(1000, hi)))
    return info, lines, W, H, sym, name, mirror, est, last
if __name__ == '__main__':
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)
    for f in sys.argv[2:]:
        info, lines, W, H, sym, name, mirror, est, last = estimate(f)
        out = []
        for l in lines:
            q = l.split()
            if q and q[0] == 'TILE':
                x, y = int(q[1]), int(q[2]); key = min((x, y), mirror((x, y)))
                lo, hi = est.get(key, (0, 0))
                out.append(f'TILE {x} {y} {lo} {hi}')
            else:
                out.append(l)
        fn = os.path.join(out_dir, name.lower().replace(' ', '_') + '.map')
        open(fn, 'w').write('\n'.join(out) + '\n')
        print(fn, W, H, sym, 'rounds', last, 'spawn pairs', len(est))
