import sys, glob
sys.path.insert(0, '/Users/quasarpark/meow-loop/loop/tools')
from terr13 import one
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
if __name__ == '__main__':
    with ProcessPoolExecutor(3) as ex:
        for pat in sys.argv[1:]:
            fs = sorted(glob.glob(pat))
            rs = list(ex.map(one, [(f, 'A' if f.endswith('_0.replay') else 'B', 'W') for f in fs]))
            n = max(1, len(rs)); occ = Counter(); dth = Counter()
            for r in rs: occ.update(r['occ']); dth.update(r['dth'])
            out = []
            for s in ('us', 'them'):
                d = sum(v for k, v in dth.items() if k[:3] == (s, 0, 1) and k[3] in (2, 3))
                to = sum(v for k, v in occ.items() if k[0] == s)
                out.append('%s tightE L2-3 deaths/game %.1f occ %.3f' % (s, d / n, occ[s, 0, 1] / max(1, to)))
            print(pat, 'games', len(rs), ' | '.join(out))
