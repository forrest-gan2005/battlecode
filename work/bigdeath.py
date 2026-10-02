import sys, os, glob, re
sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay
from collections import deque, Counter
from concurrent.futures import ProcessPoolExecutor
R = ['wall', 'self', 'body', 'head', 'none']
def run(f):
    m = re.search(r'_(\d+)_([01])\.replay$', f); side = 'A' if m.group(2) == '0' else 'B'
    info, _, team_of = replay.parse(f)
    bodies = {}
    for l in info['map'].splitlines():
        q = l.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    c = Counter(); actor = None; upd = 0; mx = Counter()
    for ev in replay.load(f).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'turnStart': actor = pl.i32(0); upd = 0
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            if did == actor: upd += 1
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4); bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A','B')[pl.u16(8)]
        elif k == 'dragonDeath':
            did = pl.i32(0); b = bodies.pop(did, deque()); L = len(b)
            if team_of.get(did) == side and L >= 15:
                own = did == actor
                c[(R[pl.u16(4)] if pl.u16(4) < 5 else '?', 'own-turn' if own else 'other-turn', 'multi' if own and upd >= 1 else '-')] += 1
                c['n'] += 1; c['len'] += L
    return c
if __name__ == '__main__':
    for tag in sys.argv[1:]:
        files = glob.glob(f'ab2/{tag}_*_50[01]_[01].replay')
        tot = Counter()
        with ProcessPoolExecutor(8) as ex:
            for c in ex.map(run, files): tot.update(c)
        n = tot.pop('n'); L = tot.pop('len')
        print(tag, 'games', len(files), 'big deaths', n, 'length lost', L)
        for k, v in sorted(tot.items(), key=lambda x: -x[1])[:8]: print('   ', k, v)
