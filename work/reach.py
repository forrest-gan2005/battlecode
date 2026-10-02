import sys
from collections import deque
def load(f):
    L = open(f).read().splitlines(); W, H = map(int, L[0].split()[1:3])
    E = {}; T = {}; D = []; P = {}
    for l in L:
        q = l.split()
        if not q: continue
        if q[0] == 'EDGE':
            E[int(q[1])] = int(q[2])
            if int(q[2]) == 2: P.setdefault(int(q[3]), []).append(int(q[1]))
        elif q[0] == 'TILE': T[(int(q[1]), int(q[2]))] = (int(q[3]), int(q[4]))
        elif q[0] == 'DRAGON' and len(q) > 4: D.append((int(q[1]), (int(q[3]), int(q[4])), int(q[2])))
    return W, H, E, T, D, P
def nbrs(W, H, E, x, y):
    S = 2 * (W + 1)
    n = E.get(y * S + x, 0); s = E.get(((y + 1) % H) * S + x, 0) if y + 1 < H else E.get(H * S + x, E.get(x, 0))
    w = E.get(y * S + (W + 1) + x, 0); e = E.get(y * S + (W + 1) + x + 1, 0)
    out = []
    if n == 0: out.append((x, (y - 1) % H))
    if s == 0: out.append((x, (y + 1) % H))
    if w == 0: out.append(((x - 1) % W, y))
    if e == 0: out.append(((x + 1) % W, y))
    return out
def bfs(W, H, E, s):
    d = {s: 0}; q = deque([s])
    while q:
        c = q.popleft()
        for n in nbrs(W, H, E, *c):
            if n not in d: d[n] = d[c] + 1; q.append(n)
    return d
if __name__ == '__main__':
    W, H, E, T, D, P = load(sys.argv[1])
    print('size', W, H, 'portals', {k: v for k, v in P.items()})
    for team, h, ln in D:
        d = bfs(W, H, E, h)
        cls = {}
        for c, (a, b) in T.items():
            k = 'fount' if 0 < b <= 1 else ('fast' if 0 < b <= 60 else ('slow' if b > 60 else 'never'))
            cls.setdefault(k, []).append(c)
        rep = {k: (sum(1 for c in v if c in d), len(v), min((d[c] for c in v if c in d), default=None)) for k, v in cls.items()}
        print('team', team, 'head', h, 'len', ln, 'region', len(d), 'of', W * H, '| class: (reachable w/o portal, total, nearest dist)', rep)
