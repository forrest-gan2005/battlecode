import os, sys
SRC = '/Users/quasarpark/meow-loop/tune_runs/variants'
OUT = '/Users/quasarpark/meow-loop/tune_runs/variants_sq'
os.makedirs(OUT, exist_ok=True)
for fn in sorted(os.listdir(SRC)):
    L = open(os.path.join(SRC, fn)).read().splitlines()
    W, H = map(int, L[0].split()[1:3])
    sym = next((l.split()[1] for l in L if l.startswith('SYMMETRY')), 'xy')
    T = (lambda x, y: (W - 1 - x, H - 1 - y)) if sym == 'xy' else (lambda x, y: (W - 1 - x, y)) if sym == 'y' else (lambda x, y: (x, H - 1 - y))
    kind = {}
    for l in L:
        p = l.split()
        if p and p[0] == 'EDGE':
            kind[int(p[1])] = int(p[2])
    blocked_tile = {(int(p[1]), int(p[2])) for p in (l.split() for l in L) if p and p[0] == 'TILE' and False}
    def north(x, y): return y * 2 * (W + 1) + x
    def west(x, y): return y * 2 * (W + 1) + (W + 1) + x
    def passable(a, b):
        (x, y), (u, v) = a, b
        if u == x:
            e = north(x, y) if (v - y) % H == H - 1 else north(x, v)
        else:
            e = west(x, y) if (u - x) % W == W - 1 else west(u, y)
        return kind.get(e, 0) == 0
    drag = [l for l in L if l.startswith('DRAGON ')]
    occupied = set()
    parsed = []
    for l in drag:
        p = l.split(); cells = [(int(p[3 + 2 * k]), int(p[4 + 2 * k])) for k in range(int(p[2]))]
        parsed.append((int(p[1]), cells, l)); occupied.update(cells)
    def openness(c):
        seen = {c}; frontier = [c]
        for _ in range(4):
            nxt = []
            for x, y in frontier:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = ((x + dx) % W, (y + dy) % H)
                    if n not in seen and n not in occupied and passable((x, y), n):
                        seen.add(n); nxt.append(n)
            frontier = nxt
        return len(seen)
    A = [d for d in parsed if d[0] == 0]
    best = max(A, key=lambda d: openness(d[1][0]))
    mate = next((d for d in parsed if d[0] == 1 and d[1][0] == T(*best[1][0])), None)
    if mate is None:
        mate = max((d for d in parsed if d[0] == 1), key=lambda d: openness(d[1][0]))
    rest = [d for d in parsed if d is not best and d is not mate]
    ra = [d for d in rest if d[0] == 0]; rb = [d for d in rest if d[0] == 1]
    order = [best, mate] + [x for pair in zip(ra, rb) for x in pair]
    out = []; done = False
    for l in L:
        if l.startswith('DRAGON '):
            if not done:
                out.extend(d[2] for d in order); done = True
            continue
        out.append(l)
    name = fn[:-4] + '_sq'
    out = [('MAP_NAME ' + name) if l.startswith('MAP_NAME') else l for l in out]
    open(os.path.join(OUT, name + '.map'), 'w').write('\n'.join(out) + '\n')
    print(name, 'queen openness', openness(best[1][0]), 'orig first', openness(A[0][1][0]))
