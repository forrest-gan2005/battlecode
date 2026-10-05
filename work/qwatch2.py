#!/usr/bin/env python3
"""Per-round queen tracker for ladder or local replays.

usage: python3 qwatch2.py REPLAY... [--ours A|B] [--json out.json]

The queens are dragons 0 and 1; each one's team comes from its DRAGON line.
For every queen it prints length over time, splits, sprints, eats (natural vs corpse),
enemy-head distance (torus manhattan and BFS through open, unoccupied cells),
escort counts, how far it roams from its spawn, danger rounds and how they ended.
"""
import json, os, sys
from collections import defaultdict, deque, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

REASONS = ['wall', 'self', 'body', 'head', 'none']
DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]


class Board:
    def __init__(self, text):
        lines = text.splitlines()
        self.W, self.H = map(int, lines[0].split()[1:3])
        self.edges = {}
        self.portal_of = {}
        self.tiles = {}
        pairs = defaultdict(list)
        for l in lines:
            q = l.split()
            if not q:
                continue
            if q[0] == 'EDGE':
                i, k = int(q[1]), int(q[2])
                self.edges[i] = k
                if k == 2:
                    pairs[int(q[3])].append(i)
            elif q[0] == 'TILE':
                self.tiles[(int(q[1]), int(q[2]))] = (int(q[3]), int(q[4]))
        for p, ids in pairs.items():
            if len(ids) == 2:
                self.portal_of[ids[0]] = ids[1]
                self.portal_of[ids[1]] = ids[0]
        self.name = next((l[9:] for l in lines if l.startswith('MAP_NAME')), '?')

    def eid(self, x, y, d):
        W, H = self.W, self.H
        S = W + 1
        if d == 0:
            return 2 * y * S + x
        if d == 2:
            return 2 * ((y + 1) % H) * S + x
        if d == 3:
            return (2 * y + 1) * S + x
        return (2 * y + 1) * S + (x + 1) % W

    def kind(self, x, y, d):
        return self.edges.get(self.eid(x, y, d), 0)

    def open_nbrs(self, c):
        x, y = c
        for d, (dx, dy) in enumerate(DIRS):
            if self.kind(x, y, d) == 0:
                yield ((x + dx) % self.W, (y + dy) % self.H)

    def man(self, a, b):
        dx = abs(a[0] - b[0]); dy = abs(a[1] - b[1])
        return min(dx, self.W - dx) + min(dy, self.H - dy)


def bfs(board, start, blocked, cap):
    dist = {start: 0}
    q = deque([start])
    while q:
        c = q.popleft()
        if dist[c] >= cap:
            continue
        for n in board.open_nbrs(c):
            if n in dist or n in blocked:
                continue
            dist[n] = dist[c] + 1
            q.append(n)
    return dist


def reach_of(length):
    return max(1, length - 1)


def track(path, cap=8):
    info, _, _ = replay.parse(path)
    board = Board(info['map'])
    bodies, team_of = {}, {}
    for line in info['map'].splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
    queens = {team_of[0]: 0, team_of[1]: 1}
    spawn = {t: bodies[q][0] for t, q in queens.items()}
    stats = {t: dict(id=q, len={}, splits=[], sprints=0, steps=0, eats=0, corpse_eats=0, death=None,
                     near=[], bfs=[], escort3=[], escort5=[], away=[], cells=set(), danger=[], kills_near=[],
                     moves=0, enemy_seen=0) for t, q in queens.items()}
    corpse_cells = {}
    rnd = 0
    last_len = {d: len(b) for d, b in bodies.items()}
    pending_moves = defaultdict(int)
    root = replay.load(path).root()

    def snapshot():
        occ = {}
        heads = defaultdict(list)
        for d, b in bodies.items():
            for i, c in enumerate(b):
                occ[c] = (d, i)
            if b:
                heads[team_of[d]].append((d, b[0], len(b)))
        for t, q in queens.items():
            st = stats[t]
            if q not in bodies or st['death'] is not None:
                continue
            h = bodies[q][0]
            st['len'][rnd] = len(bodies[q])
            st['cells'].add(h)
            st['away'].append(board.man(h, spawn[t]))
            enemy = [x for x in heads['B' if t == 'A' else 'A']]
            near = min((board.man(h, e[1]) for e in enemy), default=99)
            st['near'].append(near)
            if near <= 3:
                st['enemy_seen'] += 1
            blocked = {c for c in occ if c != h}
            dist = bfs(board, h, blocked - {e[1] for e in enemy}, cap)
            best = 99
            threat = None
            for d, e, L in enemy:
                if e in dist and dist[e] < best:
                    best = dist[e]; threat = (d, e, L)
            st['bfs'].append(best)
            allies = [x for x in heads[t] if x[0] != q]
            st['escort3'].append(sum(1 for a in allies if board.man(h, a[1]) <= 3))
            st['escort5'].append(sum(1 for a in allies if board.man(h, a[1]) <= 5))
            if threat and best <= reach_of(threat[2]) + 1 and best <= 4:
                st['danger'].append(dict(r=rnd, d=best, enemy=threat[0], elen=threat[2], qlen=len(bodies[q]),
                                         esc=st['escort3'][-1]))

    for ev in root.pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]
        pl = ev.pointer(0)
        if k == 'roundStart':
            if rnd:
                snapshot()
            rnd = pl.i32(0)
        elif k == 'dragonAction':
            did = pl.i32(0)
            a = pl.pointer(0)
            if a and a.u16(0) == 0:
                pending_moves[did] = 0
        elif k == 'dragonUpdate':
            did = pl.i32(0)
            h = replay.point(pl.pointer(0))
            tl = replay.point(pl.pointer(1))
            b = bodies.setdefault(did, deque())
            before = len(b)
            moved = bool(b) and b[0] != h
            if not b or b[0] != h:
                b.appendleft(h)
            while len(b) > 1 and b[-1] != tl:
                b.pop()
            if did in (0, 1):
                t = team_of[did]
                st = stats[t]
                if moved:
                    pending_moves[did] += 1
                    st['steps'] += 1
                    if pending_moves[did] == 2:
                        st['sprints'] += 1
                if len(b) > before and moved:
                    st['eats'] += len(b) - before
                    if h in corpse_cells and rnd - corpse_cells[h] < 60:
                        st['corpse_eats'] += len(b) - before
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            team = ('A', 'B')[pl.u16(8)]
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0))
            bodies[ch] = deque(replay.point(x) for x in pl.pointer(1))
            team_of[pa] = team_of[ch] = team
            if pa in (0, 1):
                stats[team_of[pa]]['splits'].append((rnd, len(bodies[pa]), len(bodies[ch])))
        elif k == 'dragonDeath':
            did = pl.i32(0)
            why = pl.u16(4)
            b = bodies.pop(did, deque())
            for i, c in enumerate(b):
                if i % 2 == 0:
                    corpse_cells[c] = rnd
            if did in (0, 1):
                stats[team_of[did]]['death'] = (rnd, REASONS[why] if why < 5 else '?', len(b))
            elif b:
                for t, q in queens.items():
                    if q in bodies and team_of.get(did) != t and board.man(bodies[q][0], b[0]) <= 3:
                        stats[t]['kills_near'].append((rnd, did, len(b), REASONS[why] if why < 5 else '?'))
    snapshot()
    res = root.pointer(4)
    qlen = {'A': res.pointer(0).i32(12), 'B': res.pointer(1).i32(12)}
    longest = {'A': res.pointer(0).i32(4), 'B': res.pointer(1).i32(4)}
    total = {'A': res.pointer(0).i32(8), 'B': res.pointer(1).i32(8)}
    winner = ('A', 'B')[res.u16(6)] if res.u16(4) == 1 else None
    return dict(map=board.name, cells=board.W * board.H, winner=winner, qlen=qlen, longest=longest, total=total,
                end=info['endReason'], stats=stats)


def pct(xs, f):
    return sum(1 for x in xs if f(x)) / max(1, len(xs))


def report(g, ours):
    them = 'B' if ours == 'A' else 'A'
    print(f"== {g['map']} ({g['cells']} cells) winner={'us' if g['winner'] == ours else 'them'} end={g['end']} "
          f"queen us {g['qlen'][ours]} them {g['qlen'][them]} | longest us {g['longest'][ours]} them {g['longest'][them]} "
          f"| total us {g['total'][ours]} them {g['total'][them]}")
    for side, t in (('us', ours), ('them', them)):
        st = g['stats'][t]
        L = st['len']
        cps = [r for r in (25, 50, 100, 150, 200, 300, 400, 499) if r in L]
        lens = ' '.join(f"r{r}:{L[r]}" for r in cps)
        near = st['near']; bf = st['bfs']
        print(f"  {side:4s} q{st['id']} death={st['death']} len[{lens}] splits={len(st['splits'])} "
              f"{[(r, p, c) for r, p, c in st['splits'][:8]]} sprints={st['sprints']} eats={st['eats']} (corpse {st['corpse_eats']})")
        if near:
            print(f"       enemy head manhattan<=2 {pct(near, lambda x: x <= 2):.0%} <=4 {pct(near, lambda x: x <= 4):.0%} "
                  f"| bfs<=2 {pct(bf, lambda x: x <= 2):.0%} <=4 {pct(bf, lambda x: x <= 4):.0%} | escort<=3 mean "
                  f"{sum(st['escort3']) / len(near):.2f} <=5 {sum(st['escort5']) / len(near):.2f} | away from spawn median "
                  f"{sorted(st['away'])[len(st['away']) // 2]} max {max(st['away'])} | unique cells {len(st['cells'])} "
                  f"| danger rounds {len(st['danger'])} | enemy kills within 3 {len(st['kills_near'])}")


if __name__ == '__main__':
    args = sys.argv[1:]
    ours = 'A'
    out = None
    if '--ours' in args:
        i = args.index('--ours'); ours = args[i + 1]; del args[i:i + 2]
    if '--json' in args:
        i = args.index('--json'); out = args[i + 1]; del args[i:i + 2]
    games = []
    for p in args:
        g = track(p)
        g['file'] = os.path.basename(p)
        report(g, ours)
        for st in g['stats'].values():
            st['cells'] = len(st['cells'])
        games.append(g)
    if out:
        json.dump(games, open(out, 'w'))
