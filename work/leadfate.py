import sys, os, pickle
sys.path.insert(0, '/Users/UNSW/battlecode'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc, dtrace
from concurrent.futures import ProcessPoolExecutor
def one(arg):
    gid, ours = arg
    p = os.path.join('nr', gid + '.replay')
    info, out, team_of = bc.walk(p)
    them = 'B' if ours == 'A' else 'A'
    rows, _ = dtrace.run(p, 500)
    dead = {r[2]: r for r in rows}
    hist = {}
    for e in out:
        if e[0] == 'round' and e[1] in (300, 350, 400, 450, 480, 499):
            hist[e[1]] = {t: sorted(((l, d) for d, l in e[2].items() if team_of.get(d) == t and l > 0), reverse=True)[:3] for t in (ours, them)}
    lead = hist[400][ours][0][1] if hist.get(400) and hist[400][ours] else None
    traj = []
    for r in (300, 350, 400, 450, 480, 499):
        if r not in hist: continue
        mine = dict((d, l) for l, d in hist[r][ours])
        traj.append(f"r{r} 我{[l for l, d in hist[r][ours]]} 敌{[l for l, d in hist[r][them]]}")
    fate = dead.get(lead)
    return gid, lead, fate, traj
if __name__ == '__main__':
    res = pickle.load(open('lossan.pkl', 'rb'))
    side = {}
    for line in open('nr_v55all.txt'):
        p = line.split()
        for g in p[5].split(','): side[g.split(':')[0]] = p[4]
    sel = [r for r in res if not r['win'] and r['how'] in ('longest',) and r['last'] >= 499]
    with ProcessPoolExecutor(6) as ex: out = list(ex.map(one, [(r['gid'], side[r['gid']]) for r in sel]))
    meta = {r['gid']: r for r in sel}
    for gid, lead, fate, traj in out:
        r = meta[gid]
        print(gid, r['map'][:10], r['opp'][:10], 'Q', r['oq'], r['tq'], '| r400领队', lead, '死亡' if fate else '', fate[:5] if fate else '')
        print('   ', ' | '.join(traj))
