import sys, glob
sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
R = ['wall', 'self', 'body', 'head', 'none']
def one(path):
    info, ev, team = replay.parse(path)
    cells = sum(1 for l in info['map'].splitlines() if l.startswith('ROW')) 
    out = []
    qlen = {0: [], 1: []}; last = {0: 0, 1: 0}; dead = {}
    splits = Counter()
    for e in ev:
        if e['kind'] == 'update' and e['id'] in (0, 1):
            last[e['id']] = e['length']
        elif e['kind'] == 'split' and e['id'] in (0, 1):
            splits[e['id']] += 1; last[e['id']] = e['parentLength']
        elif e['kind'] == 'death' and e['id'] in (0, 1):
            dead[e['id']] = (e['round'], e['reason'], e['length'])
    for q in (0, 1):
        out.append((q, dead.get(q), splits[q], last[q]))
    return path, info['winner'], out
if __name__ == '__main__':
    fs = sorted(set(sum((glob.glob(p) for p in sys.argv[1:]), [])))
    with ProcessPoolExecutor(6) as ex: rs = list(ex.map(one, fs))
    rc = Counter(); rounds = []; lens = []; alive = 0; spl = []
    for p, w, out in rs:
        for q, d, s, l in out:
            spl.append(s)
            if d is None: alive += 1; continue
            rc[d[1]] += 1; rounds.append(d[0]); lens.append(d[2])
    rounds.sort(); lens.sort()
    n = len(rs) * 2
    print('games', len(rs), 'queens', n, 'alive at end', alive)
    print('death reasons', dict(rc))
    if rounds:
        q = lambda a, f: a[int(f * (len(a) - 1))]
        print('death round p10/p25/med/p75/p90', [q(rounds, f) for f in (.1, .25, .5, .75, .9)])
        print('death length p10/med/p90', [q(lens, f) for f in (.1, .5, .9)])
        print('deaths before r50', sum(r < 50 for r in rounds), 'r50-150', sum(50 <= r < 150 for r in rounds), 'r150-300', sum(150 <= r < 300 for r in rounds), 'r300+', sum(r >= 300 for r in rounds))
    print('queen splits per queen mean %.1f' % (sum(spl) / max(1, len(spl))))
