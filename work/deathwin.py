import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dtrace
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
def one(gid):
    rows, c = dtrace.run(os.path.join('nr', gid + '.replay'), 120)
    return gid, rows
if __name__ == '__main__':
    res = pickle.load(open('lossan.pkl', 'rb'))
    maps = sys.argv[1].split(',')
    sel = [r for r in res if r['map'] in maps]
    with ProcessPoolExecutor(6) as ex: out = dict(ex.map(one, [r['gid'] for r in sel]))
    for w in (True, False):
        agg = Counter(); n = 0
        for r in sel:
            if r['win'] != w: continue
            n += 1
            for rnd, side, did, ln, reason, h, st, near in out[r['gid']]:
                win = '0-50' if rnd < 50 else ('50-100' if rnd < 100 else '100-120')
                agg[win, side, reason.split('/')[0] if not reason.startswith('head') else reason] += 1
        print('WIN' if w else 'LOSS', n, 'games, deaths per game:')
        for win in ('0-50', '50-100'):
            for side in ('us', 'them'):
                items = sorted(((k[2], v) for k, v in agg.items() if k[0] == win and k[1] == side), key=lambda x: -x[1])
                print(f"  {win:6s} {side:4s} total {sum(v for _, v in items)/n:4.1f} | " + ' '.join(f"{k}:{v/n:.1f}" for k, v in items))
