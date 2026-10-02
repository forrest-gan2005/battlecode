import pickle
from collections import Counter
out = pickle.load(open('/Users/quasarpark/meow-loop/loop/tools/splitlen.pkl', 'rb'))
def grp(r): return ('S' if r['W']*r['H'] <= 800 else 'M' if r['W']*r['H'] <= 1200 else 'B')
for g in ('S', 'M', 'B'):
    for res in (True, False):
        rs = [r for r in out if grp(r) == g and r['win'] == res]
        if not rs: continue
        n = len(rs)
        print(f'== size {g} ({"<=800" if g=="S" else "801-1200" if g=="M" else ">1200"}) {"W" if res else "L"} N={n}')
        for lo, hi in ((50, 100), (100, 150), (150, 300)):
            c = Counter(); pl = Counter()
            for r in rs:
                for (rd, s, b, a, ch, q) in r['sp']:
                    if lo <= rd < hi and not q:
                        c[s] += 1; pl[s, min(b, 9)] += 1
            h = Counter()
            for r in rs:
                for (s, ph, L), v in r['hist'].items():
                    if lo // 50 <= ph < hi // 50: h[s, L] += v
            line = f'  r{lo}-{hi} splits/g {c["us"]/n:.1f}:{c["them"]/n:.1f}  parentL '
            line += ' '.join(f'{L}:{pl["us",L]/max(1,c["us"]):.2f}/{pl["them",L]/max(1,c["them"]):.2f}' for L in range(4, 10))
            tu = sum(v for (s, L), v in h.items() if s == 'us'); tt = sum(v for (s, L), v in h.items() if s == 'them')
            line += '  mix ' + ' '.join(f'{L}:{h["us",L]/max(1,tu):.2f}/{h["them",L]/max(1,tt):.2f}' for L in range(2, 10))
            line += f'  dr/g {tu/n/ (hi-lo):.1f}:{tt/n/(hi-lo):.1f}'
            print(line)
