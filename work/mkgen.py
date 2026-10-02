import os, random, sys
from collections import deque

OUT = '/Users/UNSW/battlecode/tune_runs/genmaps'
PALETTE = [((0, 0), 30), ((1, 1000), 8), ((1, 600), 8), ((1, 300), 10), ((1, 200), 10), ((1, 150), 8),
           ((1, 100), 10), ((1, 60), 6), ((1, 30), 5), ((5, 30), 5)]
STYLES = ['open', 'blobs', 'maze', 'rooms', 'islands', 'stripes']


def rate(ab):
    return 0.0 if ab == (0, 0) else 2.0 / (ab[0] + ab[1])


def make(seed, style=None, size=None):
    rng = random.Random(seed)
    style = style or rng.choice(STYLES)
    if size is None:
        size = rng.choice(['small', 'medium', 'large', 'large'])
    W, H = {'small': (rng.randrange(16, 28), rng.randrange(10, 20)),
            'medium': (rng.randrange(28, 44), rng.randrange(18, 34)),
            'large': (rng.randrange(44, 65), rng.randrange(32, 65))}[size]
    sym = rng.choice(['x', 'y', 'xy'])
    if sym == 'xy':
        T = lambda x, y: (W - 1 - x, H - 1 - y)
    elif sym == 'y':
        T = lambda x, y: (W - 1 - x, y)
    else:
        T = lambda x, y: (x, H - 1 - y)
    border = rng.random() < 0.5
    block = set()

    def put(x, y):
        x %= W
        y %= H
        block.add((x, y))
        block.add(T(x, y))

    if style == 'blobs':
        for _ in range(W * H // rng.choice([40, 70, 120])):
            cx, cy, r = rng.randrange(W), rng.randrange(H), rng.choice([1, 1, 2, 3])
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if abs(dx) + abs(dy) <= r and rng.random() < 0.8:
                        put(cx + dx, cy + dy)
    elif style == 'maze':
        step = rng.choice([2, 3, 4])
        for x in range(0, W, step):
            for y in range(H):
                if rng.random() < 0.75:
                    put(x, y)
        for y in range(0, H, step):
            for x in range(W):
                if (x % step) and rng.random() < 0.35:
                    put(x, y)
        for _ in range(W * H // 6):
            x, y = rng.randrange(W), rng.randrange(H)
            block.discard((x, y))
            block.discard(T(x, y))
    elif style == 'rooms':
        rw, rh = rng.choice([6, 8, 10]), rng.choice([5, 6, 8])
        for x in range(0, W, rw):
            for y in range(H):
                put(x, y)
        for y in range(0, H, rh):
            for x in range(W):
                put(x, y)
        for x in range(0, W, rw):
            for y in range(0, H, rh):
                for k in range(rng.choice([1, 2])):
                    if rng.random() < 0.7:
                        dy = rng.randrange(1, rh)
                        block.discard((x, (y + dy) % H))
                        block.discard(T(x, (y + dy) % H))
                    if rng.random() < 0.7:
                        dx = rng.randrange(1, rw)
                        block.discard(((x + dx) % W, y))
                        block.discard(T((x + dx) % W, y))
    elif style == 'islands':
        for x in range(W):
            for y in range(H):
                put(x, y)
        for _ in range(rng.randrange(4, 10)):
            cx, cy = rng.randrange(W), rng.randrange(H)
            rx, ry = rng.randrange(2, 7), rng.randrange(2, 6)
            for dx in range(-rx, rx + 1):
                for dy in range(-ry, ry + 1):
                    if (dx * dx) / (rx * rx + 0.1) + (dy * dy) / (ry * ry + 0.1) <= 1.0:
                        for c in ((cx + dx) % W, (cy + dy) % H), T((cx + dx) % W, (cy + dy) % H):
                            block.discard(c)
        for _ in range(rng.randrange(6, 14)):
            x, y = rng.randrange(W), rng.randrange(H)
            horizontal = rng.random() < 0.5
            for k in range(rng.randrange(6, max(8, W // 2))):
                c = ((x + k) % W, y) if horizontal else (x, (y + k) % H)
                block.discard(c)
                block.discard(T(*c))
    elif style == 'stripes':
        gap = rng.choice([3, 4, 5])
        vertical = rng.random() < 0.5
        for a in range(0, W if vertical else H, gap):
            for b in range(H if vertical else W):
                if rng.random() < 0.85:
                    put(a, b) if vertical else put(b, a)

    if border:
        for x in range(W):
            put(x, 0)
        for y in range(H):
            put(0, y)

    open_cells = [(x, y) for x in range(W) for y in range(H) if (x, y) not in block]

    def comp(start):
        seen = {start}
        q = deque([start])
        while q:
            x, y = q.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                c = ((x + dx) % W, (y + dy) % H)
                if c not in block and c not in seen:
                    seen.add(c)
                    q.append(c)
        return seen

    if len(open_cells) < W * H * 0.35:
        return None
    main = max((comp(c) for c in rng.sample(open_cells, min(6, len(open_cells)))), key=len)
    if len(main) < W * H * 0.3:
        return None

    types, weights = zip(*PALETTE)
    for _ in range(100):
        n = max(5, W * H // rng.choice([25, 40, 70]))
        seeds = [((rng.randrange(W), rng.randrange(H)), rng.choices(types, weights)[0]) for _ in range(n)]

        def dist(a, b):
            dx = abs(a[0] - b[0])
            dy = abs(a[1] - b[1])
            return min(dx, W - dx) + min(dy, H - dy)

        par = {}
        for x in range(W):
            for y in range(H):
                c = min((x, y), T(x, y))
                if c not in par:
                    par[c] = min(seeds, key=lambda s: (dist(s[0], c), s[0]))[1]
        for c in rng.sample(sorted(par), min(rng.choice([0, 0, 2, 4, 6, 8]), len(par))):
            par[c] = (1, 1)
        full = {(x, y): ((0, 0) if (x, y) in block else par[min((x, y), T(x, y))]) for x in range(W) for y in range(H)}
        dens = sum(rate(v) for v in full.values()) / (W * H) * 100
        if 0.15 <= dens <= 4.0:
            break
    else:
        return None

    starts = rng.choice([1, 1, 2, 3, 4])
    length = rng.choice([2, 3, 3, 4, 5, 7])
    dragons = []
    used = set()
    cand = [c for c in main if T(*c) in main]
    rng.shuffle(cand)
    for c in cand:
        if len(dragons) >= 2 * starts:
            break
        body = [c]
        ok = True
        while len(body) < length and ok:
            x, y = body[-1]
            opts = [((x + dx) % W, (y + dy) % H) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            opts = [o for o in opts if o in main and o not in body and o not in used]
            if not opts:
                ok = False
                break
            body.append(rng.choice(opts))
        if not ok:
            continue
        mirror = [T(*b) for b in body]
        if set(mirror) & (set(body) | used) or any(m not in main for m in mirror):
            continue
        if min(dist(b, m) for b in body for m in mirror) < 6:
            continue
        dragons.append((0, body))
        dragons.append((1, mirror))
        used.update(body)
        used.update(mirror)
    if len(dragons) < 2:
        return None

    def north(x, y):
        return y * 2 * (W + 1) + x

    def west(x, y):
        return y * 2 * (W + 1) + (W + 1) + x

    kinds = {}
    for x in range(W):
        for y in range(H):
            up = (x, (y - 1) % H)
            left = ((x - 1) % W, y)
            kn = 1 if ((x, y) in block or up in block) else 0
            kw = 1 if ((x, y) in block or left in block) else 0
            kinds[north(x, y)] = kn
            kinds[west(x, y)] = kw
            if y == 0:
                kinds[north(x, H)] = kn
            if x == 0:
                kinds[west(W, y)] = kw
    total = (2 * H + 1) * (W + 1)
    name = f'gen_{style}_{size}_{seed}'
    lines = [f'MAP {W} {H}', f'SYMMETRY {sym}', f'MAP_NAME {name}', f'TILE_COUNT {W * H}']
    for y in range(H):
        for x in range(W):
            a, b = full[(x, y)]
            lines.append(f'TILE {x} {y} {a} {b}')
    lines.append(f'EDGE_COUNT {total}')
    for i in range(total):
        lines.append(f'EDGE {i} {kinds.get(i, 0)} -1')
    lines.append(f'DRAGON_COUNT {len(dragons)}')
    for team, body in dragons:
        lines.append(f'DRAGON {team} {len(body)} ' + ' '.join(f'{x} {y}' for x, y in body))
    lines.append('END')
    return name, '\n'.join(lines) + '\n'


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    want = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    made = 0
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    while made < want:
        r = make(seed)
        seed += 1
        if r:
            name, text = r
            open(os.path.join(OUT, name + '.map'), 'w').write(text)
            made += 1
            print(name)
