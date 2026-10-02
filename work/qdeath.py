import sys, os
sys.path.insert(0, '/Users/UNSW/battlecode'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay, wipe, ourside
from collections import deque, Counter
R = ['wall', 'self', 'body', 'head', 'none']
def run(p):
    ours = ourside.ours_of(p)
    info, _, team_of = replay.parse(p)
    lines = info['map'].splitlines()
    edges = {}
    W, H = map(int, lines[0].split()[1:3])
    for q in (x.split() for x in lines):
        if q and q[0] == 'EDGE': edges[int(q[1])] = int(q[2])
    bodies = {}
    for line in lines:
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    qid = 0 if team_of.get(0) == ours else 1
    rnd = 0; mover = None; ms = 0; out = {}; portal_moves = 0
    for ev in replay.load(p).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart': rnd = pl.i32(0)
        elif k == 'dragonAction':
            mover = pl.i32(0); a = pl.pointer(0); ms = 0
            if a and a.u16(0) == 0:
                try: ms = len(a.pointer(0))
                except Exception: ms = 0
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            if did == qid and b and abs(h[0]-b[0][0]) + abs(h[1]-b[0][1]) > 1 and ms <= 1: portal_moves += 1
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4); bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A','B')[pl.u16(8)]
        elif k == 'dragonDeath':
            did = pl.i32(0); r = pl.u16(4); b = bodies.pop(did, deque())
            if did == qid:
                reason = R[r] if r < 5 else str(r)
                if r == 3: reason = 'ram(self-initiated)' if mover == did else ('rammed_by_enemy' if team_of.get(mover) != ours else 'rammed_by_ally')
                out = dict(round=rnd, reason=reason, len=len(b))
    return out, portal_moves
def safe(f):
    try: return run(f)
    except Exception: return None
if __name__ == '__main__':
    c = Counter(); rounds = []; lens = Counter(); pm = 0; n = 0
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(8) as ex: res = list(ex.map(safe, sys.argv[1:]))
    for r in res:
        if r is None: continue
        o, p = r
        n += 1; pm += p > 0
        if o: c[o['reason']] += 1; rounds.append(o['round']); lens[min(o['len'], 6)] += 1
        else: c['alive'] += 1
    import statistics
    print(n, 'games; queen death:', dict(c), 'median round', statistics.median(rounds) if rounds else None, 'len at death', dict(sorted(lens.items())), 'games with queen portal use', pm)
