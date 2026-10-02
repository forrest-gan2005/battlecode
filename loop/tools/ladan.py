import sys, os, pickle
sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay
from collections import deque, Counter
from concurrent.futures import ProcessPoolExecutor
R = ['wall', 'self', 'body', 'head', 'none']
NR = '/Users/quasarpark/meow-loop/work/nr'
SNAP = (25, 50, 100, 150, 200, 300, 400, 499)
def one(arg):
    gid, mp, ours, opp, elo, res = arg
    p = os.path.join(NR, gid + '.replay')
    info, _, team_of = replay.parse(p)
    them = 'B' if ours == 'A' else 'A'
    side = lambda d: 'us' if team_of.get(d) == ours else 'them'
    lines = info['map'].splitlines()
    W, H = map(int, lines[0].split()[1:3])
    bodies = {}
    for line in lines:
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    qid = {('us' if team_of[0] == ours else 'them'): 0, ('us' if team_of[1] == ours else 'them'): 1}
    rnd = 0; mover = None; deaths = []; snaps = {}; splits = Counter(); eat = Counter(); qlen = {}; qmax = {'us': 0, 'them': 0}
    def snap():
        s = {}
        for t in ('us', 'them'):
            ls = sorted((len(b) for d, b in bodies.items() if side(d) == t and b), reverse=True)
            s[t] = (sum(ls), len(ls), ls[0] if ls else 0)
        return s
    for ev in replay.load(p).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart':
            rnd = pl.i32(0)
            if rnd in SNAP: snaps[rnd] = snap()
        elif k == 'dragonAction': mover = pl.i32(0)
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            before = len(b)
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
            if len(b) > before and before > 0:
                ph = 0 if rnd < 100 else 1 if rnd < 300 else 2
                eat[side(did), ph] += len(b) - before
            if did in (0, 1):
                t = 'us' if did == qid['us'] else 'them'; qmax[t] = max(qmax[t], len(b))
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
            splits[side(pa), 0 if rnd < 100 else 1 if rnd < 300 else 2] += 1
        elif k == 'dragonDeath':
            did = pl.i32(0); r = pl.u16(4); b = bodies.pop(did, deque())
            reason = R[r] if r < 5 else str(r)
            if r == 3: reason = 'head_ram' if mover == did else 'head_rammed'
            if r == 2: reason = 'body_own' if False else 'body'
            h = b[0] if b else None
            near = min((abs(h[0]-ob[0][0]) + abs(h[1]-ob[0][1]) for d, ob in bodies.items() if ob and side(d) != side(did)), default=99) if h else 99
            deaths.append((rnd, side(did), did, len(b), reason, near, did in (0, 1)))
    snaps['end'] = snap()
    for t in ('us', 'them'):
        qlen[t] = len(bodies.get(qid[t], ())) if qid[t] in bodies else 0
    st = info['standings']
    elim = st[ours]['dragons'] == 0 or st[them]['dragons'] == 0
    qd = {t: next((d for d in deaths if d[2] == qid[t]), None) for t in ('us', 'them')}
    return dict(gid=gid, map=mp, W=W, H=H, opp=opp, elo=elo, win=res == 'W', winner_ok=(info['winner'] == ours) == (res == 'W'),
                elim=elim, last=rnd, deaths=deaths, snaps=snaps, splits=splits, eat=eat, qlen=qlen, qmax=qmax, qd=qd, st=st, ours=ours)
if __name__ == '__main__':
    args = []
    for line in open('/Users/quasarpark/meow-loop/work/nr_meow.txt'):
        q = line.split()
        if len(q) < 6: continue
        for g in q[5].split(','):
            gid, mp, res, has = g.split(':')
            if os.path.exists(os.path.join(NR, gid + '.replay')): args.append((gid, mp, q[4], q[2], int(q[3]), res))
    with ProcessPoolExecutor(4) as ex: out = list(ex.map(one, args))
    pickle.dump(out, open('/Users/quasarpark/meow-loop/loop/tools/ladan.pkl', 'wb'))
    print(len(out), 'games', sum(r['winner_ok'] for r in out), 'winner/side consistent')
