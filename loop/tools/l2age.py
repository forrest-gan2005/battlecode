import sys, os, pickle
sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay
from collections import deque, Counter
from concurrent.futures import ProcessPoolExecutor
NR = '/Users/quasarpark/meow-loop/work/nr'
R = ['wall', 'self', 'body', 'head', 'none']
def one(arg):
    gid, ours, res = arg
    p = os.path.join(NR, gid + '.replay')
    info, _, team_of = replay.parse(p)
    lines = info['map'].splitlines(); W, H = map(int, lines[0].split()[1:3])
    bodies = {}
    for line in lines:
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    side = lambda d: 'us' if team_of.get(d) == ours else 'them'
    born = {}; role = {}; c = Counter(); rnd = 0; mover = None
    for ev in replay.load(p).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart': rnd = pl.i32(0)
        elif k == 'dragonAction': mover = pl.i32(0)
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
            born[pa] = rnd; born[ch] = rnd; role[pa] = 'pa'; role[ch] = 'ch'
            if 50 <= rnd < 300: c[side(pa), 'splits'] += 1
        elif k == 'dragonDeath':
            did = pl.i32(0); r = pl.u16(4); b = bodies.pop(did, deque())
            if not (50 <= rnd < 300) or did in (0, 1): continue
            reason = R[r] if r < 5 else str(r)
            if r == 3: reason = 'head_ram' if mover == did else 'head_rammed'
            s = side(did); L = len(b)
            age = rnd - born.get(did, -999)
            ab = 'a0-1' if age <= 1 else 'a2-5' if age <= 5 else 'a6-20' if age <= 20 else 'a21+'
            grp = 'self' if reason in ('wall', 'self', 'body', 'none') else 'head'
            c[s, grp, 'L2' if L <= 2 else 'L3+', ab] += 1
            c[s, grp, 'L2' if L <= 2 else 'L3+', ab, role.get(did, '?')] += 1
            if grp == 'self': c[s, 'selfreason', reason] += 1
    return res, c
if __name__ == '__main__':
    args = []
    for line in open('/Users/quasarpark/meow-loop/work/nr_meow.txt'):
        q = line.split()
        if len(q) < 6: continue
        for g in q[5].split(','):
            gid, mp, res, has = g.split(':')
            if os.path.exists(os.path.join(NR, gid + '.replay')): args.append((gid, q[4], res))
    with ProcessPoolExecutor(3) as ex: out = list(ex.map(one, args))
    pickle.dump(out, open('/Users/quasarpark/meow-loop/loop/tools/l2age.pkl', 'wb'))
    for name, sel in (('all', lambda r: True), ('loss', lambda r: r == 'L'), ('win', lambda r: r == 'W')):
        cs = [c for r, c in out if sel(r)]; n = len(cs); T = Counter()
        for c in cs: T.update(c)
        print(f'== {name} N={n}  r50-300 per game, us:them  splits {T["us","splits"]/n:.1f}:{T["them","splits"]/n:.1f}')
        for grp in ('self', 'head'):
            for L in ('L2', 'L3+'):
                print(f'  {grp} {L} ' + '  '.join(f'{ab} {T["us",grp,L,ab]/n:.1f}:{T["them",grp,L,ab]/n:.1f}' for ab in ('a0-1', 'a2-5', 'a6-20', 'a21+')))
        print('  self a0-1 L2 by role pa/ch us', T['us','self','L2','a0-1','pa']/n, T['us','self','L2','a0-1','ch']/n, 'them', T['them','self','L2','a0-1','pa']/n, T['them','self','L2','a0-1','ch']/n)
        print('  self reasons', {k[2]: round(v/n,1) for k, v in T.items() if k[0]=='us' and k[1]=='selfreason'}, {k[2]: round(v/n,1) for k, v in T.items() if k[0]=='them' and k[1]=='selfreason'})
