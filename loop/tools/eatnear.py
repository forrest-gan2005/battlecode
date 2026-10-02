import sys, os, pickle
sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay
from collections import deque, Counter
from concurrent.futures import ProcessPoolExecutor
NR = '/Users/quasarpark/meow-loop/work/nr'
def one(arg):
    gid, ours, res, cells = arg
    p = os.path.join(NR, gid + '.replay')
    info, _, team_of = replay.parse(p)
    side = lambda d: 'us' if team_of.get(d) == ours else 'them'
    bodies = {}
    for line in info['map'].splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    rnd = 0; out = Counter()
    for ev in replay.load(p).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart': rnd = pl.i32(0)
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            before = len(b)
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
            if len(b) > before and before > 0 and 25 <= rnd < 150:
                s = side(did)
                ne = min((abs(h[0]-ob[0][0]) + abs(h[1]-ob[0][1]) for d, ob in bodies.items() if ob and side(d) != s), default=99)
                na = min((abs(h[0]-ob[0][0]) + abs(h[1]-ob[0][1]) for d, ob in bodies.items() if ob and d != did and side(d) == s), default=99)
                ph = 'r25-50' if rnd < 50 else 'r50-100' if rnd < 100 else 'r100-150'
                eb = 'e<=3' if ne <= 3 else 'e4-8' if ne <= 8 else 'e9+'
                ab = 'a<=3' if na <= 3 else 'a4+'
                out[s, ph, eb, ab] += len(b) - before
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
        elif k == 'dragonDeath':
            bodies.pop(pl.i32(0), None)
    return gid, res == 'W', cells, out
if __name__ == '__main__':
    G = pickle.load(open('/Users/quasarpark/meow-loop/loop/tools/ladan.pkl', 'rb'))
    args = [(g['gid'], g['ours'], 'W' if g['win'] else 'L', g['W'] * g['H']) for g in G if g['W'] * g['H'] <= 1200]
    with ProcessPoolExecutor(3) as ex: res = list(ex.map(one, args))
    pickle.dump(res, open('/Users/quasarpark/meow-loop/loop/tools/eatnear.pkl', 'wb'))
    print(len(res))
