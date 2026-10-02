import sys, os
sys.path.insert(0, '/Users/UNSW/battlecode'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay
from collections import deque, Counter
from concurrent.futures import ProcessPoolExecutor
R = ['wall', 'self', 'body', 'head', 'none']
def run(arg):
    path, ours, opp = arg
    info, _, team_of = replay.parse(path)
    bodies = {}
    for line in info['map'].splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    qo = 0 if team_of.get(0) == ours else 1
    death = {}; mover = None; rnd = 0
    for ev in replay.load(path).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart': rnd = pl.i32(0)
        elif k == 'dragonAction': mover = pl.i32(0)
        elif k == 'dragonDeath':
            did = pl.i32(0); r = pl.u16(4)
            if did in (0, 1):
                why = R[r] if r < 5 else str(r)
                if r == 3: why = 'ram' if mover == did else 'rammed'
                death[did] = (rnd, why)
    them = 'B' if ours == 'A' else 'A'
    st = info['standings']
    elim = st[ours]['dragons'] == 0 or st[them]['dragons'] == 0
    win = info['winner'] == ours
    how = 'elim' if elim else ('queen' if (qo in death) != ((1 - qo) in death) else 'longest')
    return dict(opp=opp, win=win, how=how, our_q=death.get(qo), their_q=death.get(1 - qo), top=st[ours]['longest'], ttop=st[them]['longest'])
if __name__ == '__main__':
    args = []
    for line in open(sys.argv[1]):
        p = line.split()
        if len(p) < 6: continue
        for g in p[5].split(','):
            gid = g.split(':')[0]
            f = os.path.join('nr', gid + '.replay')
            if os.path.exists(f): args.append((f, p[4], p[2]))
    with ProcessPoolExecutor(6) as ex: res = list(ex.map(run, args))
    c = Counter(); qd = Counter(); tq = Counter(); rounds = []
    for r in res:
        c[('W' if r['win'] else 'L') + '_' + r['how']] += 1
        if r['our_q']: qd[r['our_q'][1]] += 1; rounds.append(r['our_q'][0])
        else: qd['alive'] += 1
        tq['their_alive' if not r['their_q'] else 'their_dead'] += 1
    import statistics
    print(len(res), 'games', dict(sorted(c.items())))
    print('our queen', dict(qd), 'median death', statistics.median(rounds) if rounds else None, '| their queen', dict(tq))
