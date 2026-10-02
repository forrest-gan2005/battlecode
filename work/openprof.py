import sys, os
sys.path.insert(0, '/Users/UNSW/battlecode'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay
from collections import deque, Counter, defaultdict
R = ['wall', 'self', 'body', 'head', 'none']
def run(p, side, upto=60):
    info, _, team_of = replay.parse(p)
    lines = info['map'].splitlines(); W, H = map(int, lines[0].split()[1:3])
    bodies = {}
    for line in lines:
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    me = lambda d: team_of.get(d) == side
    root = replay.load(p).root(); rnd = 0; mover = None; c = Counter()
    for ev in root.pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart':
            rnd = pl.i32(0)
            if rnd == 50:
                c['u50'] += sum(1 for d, b in bodies.items() if b and me(d)); c['ou50'] += sum(1 for d, b in bodies.items() if b and not me(d))
                c['t50'] += sum(len(b) for d, b in bodies.items() if b and me(d)); c['ot50'] += sum(len(b) for d, b in bodies.items() if b and not me(d))
            if rnd > upto: break
        elif k == 'dragonAction': mover = pl.i32(0)
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque()); before = len(b)
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
            if len(b) > before and rnd <= 50: c['eat' if me(did) else 'oeat'] += len(b) - before
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A','B')[pl.u16(8)]
            if me(pa): c['split'] += 1; c['splitlen'] += len(bodies[pa]) + len(bodies[ch])
        elif k == 'dragonDeath':
            did = pl.i32(0); r = pl.u16(4); bodies.pop(did, None)
            if not me(did): continue
            reason = R[r] if r < 5 else str(r)
            if r == 3: reason = 'ram' if mover == did else 'rammed'
            c['d_' + reason] += 1
    c['games'] += 1; c['cells'] += W * H
    return c
def show(agg):
    for t, c in sorted(agg.items()):
        n = c['games']
        print('%-11s n%3d cells%5.0f | split %5.1f (len %.1f) eat50 %5.1f vs %5.1f | u50 %4.1f vs %4.1f tot50 %5.1f vs %5.1f | ram %4.1f rammed %4.1f wall %4.1f self %4.1f body %4.1f' % (
            t, n, c['cells']/n, c['split']/n, c['splitlen']/max(1,c['split']), c['eat']/n, c['oeat']/n, c['u50']/n, c['ou50']/n, c['t50']/n, c['ot50']/n,
            c['d_ram']/n, c['d_rammed']/n, c['d_wall']/n, c['d_self']/n, c['d_body']/n))
if __name__ == '__main__':
    agg = defaultdict(Counter)
    for l in open('ntop.txt'):
        p = l.split(); team, tid, a, b = p[0], p[1], p[3], p[4]
        side = 'A' if a == tid else 'B'
        for g in p[7].split(','):
            gid = g.split(':')[0]
            try: agg[team].update(run(f'ntop/{gid}.replay', side))
            except Exception as e: print('ERR', gid, e)
    for l in open('nus54.txt'):
        p = l.split(); side = 'A' if p[3] == '852' else 'B'
        for g in p[7].split(','):
            gid, m = g.split(':')[:2]
            f = f'nr/{gid}.replay'
            if os.path.exists(f):
                try:
                    c = run(f, side); agg['C--v54'].update(c)
                    if int(open(f,'rb').read(0) == b'') and False: pass
                except Exception as e: print('ERR', gid, e)
    show(agg)
