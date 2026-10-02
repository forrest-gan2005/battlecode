import sys, os
sys.path.insert(0, '/Users/quasarpark/meow-loop'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc, ladq
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
def run(arg):
    path, ours, opp, gid, mp = arg
    info, out, team_of = bc.walk(path)
    them = 'B' if ours == 'A' else 'A'
    snaps = {}; last = 0; peak = {ours: 0, them: 0}; eat = Counter()
    for e in out:
        if e[0] == 'round':
            last = e[1]
            for t in (ours, them):
                peak[t] = max(peak[t], sum(l for d, l in e[2].items() if team_of.get(d) == t and l > 0))
            if e[1] in (50, 100, 200, 300, 400):
                s = {}
                for t in (ours, them):
                    ls = sorted((l for d, l in e[2].items() if team_of.get(d) == t and l > 0), reverse=True)
                    s[t] = (ls[0] if ls else 0, sum(ls), len(ls))
                snaps[e[1]] = s
    q = ladq.run((path, ours, opp))
    st = info['standings']
    return dict(gid=gid, opp=opp, map=mp, win=q['win'], how=q['how'], last=last, oq=q['our_q'], tq=q['their_q'],
                us=(st[ours]['longest'], st[ours]['total'], st[ours]['dragons']), th=(st[them]['longest'], st[them]['total'], st[them]['dragons']),
                snaps={r: (s[ours], s[them]) for r, s in snaps.items()}, peak=(peak[ours], peak[them]))
if __name__ == '__main__':
    args = []
    for line in open(sys.argv[1]):
        p = line.split()
        if len(p) < 6: continue
        for g in p[5].split(','):
            gid, mp, res, has = g.split(':')
            f = os.path.join('nr', gid + '.replay')
            if os.path.exists(f): args.append((f, p[4], p[2], gid, mp))
    with ProcessPoolExecutor(6) as ex: res = list(ex.map(run, args))
    only = sys.argv[2] if len(sys.argv) > 2 else 'L'
    bymap = {}
    for r in res: bymap.setdefault(r['map'], Counter())['W' if r['win'] else 'L'] += 1
    print('per map:', ' '.join(f"{m}:{c['W']}-{c['L']}" for m, c in sorted(bymap.items())))
    for r in sorted(res, key=lambda r: (r['map'], r['opp'])):
        if only == 'L' and r['win']: continue
        f = lambda t: f"{t[0]}/{t[1]}/{t[2]}"
        sn = ' '.join(f"r{k}:{f(a)}v{f(b)}" for k, (a, b) in sorted(r['snaps'].items()))
        print(f"{r['gid']} {r['map'][:12]:12s} {r['opp'][:14]:14s} {'W' if r['win'] else 'L'}_{r['how']:7s} r{r['last']:3d} 终 {f(r['us'])} vs {f(r['th'])} 峰 {r['peak'][0]}:{r['peak'][1]} Q {r['oq']} / {r['tq']} | {sn}")
