import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay, ourside
from collections import deque, Counter
from concurrent.futures import ProcessPoolExecutor
def run(p):
    try:
        ours = ourside.ours_of(p); info, _, team_of = replay.parse(p)
    except Exception:
        return None
    bodies = {}
    for line in info['map'].splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    qid = {team_of.get(0): 0, team_of.get(1): 1}
    death = {}; L = {0: 0, 1: 0}; rnd = 0; how = {}
    for ev in replay.load(p).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart': rnd = pl.i32(0)
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A','B')[pl.u16(8)]
        elif k == 'dragonDeath':
            did = pl.i32(0); bodies.pop(did, None)
            if did in (0, 1): death[did] = rnd; how[did] = pl.u16(4)
    for d in (0, 1): L[d] = len(bodies[d]) if d in bodies and d not in death else 0
    them = 'B' if ours == 'A' else 'A'
    st = info['standings']
    elim = st[ours]['dragons'] == 0 or st[them]['dragons'] == 0
    qo, qt = L[qid[ours]], L[qid[them]]
    if elim: new = info['winner'] == ours
    elif qo != qt: new = qo > qt
    else: new = info['winner'] == ours
    return dict(win=info['winner'] == ours, new=new, elim=elim, qo=qo, qt=qt, do=death.get(qid[ours]), dt=death.get(qid[them]), ho=how.get(qid[ours]), ht=how.get(qid[them]), top=st[ours]['longest'], ttop=st[them]['longest'])
if __name__ == '__main__':
    files = []
    seen = set()
    for pat in sys.argv[1:]:
        for f in sorted(glob.glob(pat)):
            if os.path.basename(f) not in seen: seen.add(os.path.basename(f)); files.append(f)
    with ProcessPoolExecutor(8) as ex: res = [r for r in ex.map(run, files) if r]
    n = len(res); ne = [r for r in res if not r['elim']]
    print('games', n, 'non-elim', len(ne))
    print('old-rule wins', sum(r['win'] for r in res), ' queen-rule wins', sum(r['new'] for r in res))
    print('our queen alive at end (non-elim)', sum(r['qo'] > 0 for r in ne), ' theirs', sum(r['qt'] > 0 for r in ne))
    import statistics as s
    print('our queen death round median', s.median([r['do'] for r in res if r['do'] is not None] or [0]), 'theirs', s.median([r['dt'] for r in res if r['dt'] is not None] or [0]))
    print('our queen death reasons', Counter(r['ho'] for r in res if r['ho'] is not None), 'theirs', Counter(r['ht'] for r in res if r['ht'] is not None))
    for b in ((0, 100), (100, 300), (300, 501)):
        print(' deaths in r%d-%d: ours %d theirs %d' % (b[0], b[1], sum(1 for r in res if r['do'] is not None and b[0] <= r['do'] < b[1]), sum(1 for r in res if r['dt'] is not None and b[0] <= r['dt'] < b[1])))
    print('mean queen len at end when alive: ours %.1f theirs %.1f; mean longest ours %.1f theirs %.1f' % (s.mean([r['qo'] for r in ne if r['qo'] > 0] or [0]), s.mean([r['qt'] for r in ne if r['qt'] > 0] or [0]), s.mean([r['top'] for r in ne]), s.mean([r['ttop'] for r in ne])))
