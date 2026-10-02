import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ladan
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
SI = ('wall', 'self', 'body', 'none')
def arg(path):
    side = int(os.path.basename(path)[:-7].rsplit('_', 1)[1])
    return (path, '', 'A' if side == 0 else 'B', '', 0, 'W')
if __name__ == '__main__':
    groups = {}
    for pat in sys.argv[1:]:
        for f in glob.glob(pat):
            groups.setdefault(os.path.basename(f).split('_')[0], []).append(f)
    with ProcessPoolExecutor(4) as ex:
        for tag, fs in sorted(groups.items()):
            G = list(ex.map(ladan.one, [arg(f) for f in fs]))
            c = Counter(); ur = 0
            for r in G:
                s = r['snaps']
                ur += sum((s.get(a, s['end'])['us'][1] + s.get(b, s['end'])['us'][1]) / 2 * (hi - lo) for lo, hi, a, b in ((0, 100, 50, 100), (100, 300, 150, 200), (300, 500, 400, 400)))
                for d in r['deaths']:
                    if d[1] != 'us': continue
                    k = 'self' if d[4] in SI else 'head'
                    c[k] += 1
                    if k == 'self' and d[5] <= 3: c['press'] += 1
                    if d[4] == 'head_ram': c['ram'] += 1
            n = len(G)
            print('%s games %d  per 100 unit-rounds: pressure %.3f self %.3f head %.3f | per game pressure %.1f self %.1f head_ram %.1f' % (tag, n, 100 * c['press'] / ur, 100 * c['self'] / ur, 100 * c['head'] / ur, c['press'] / n, c['self'] / n, c['ram'] / n))
