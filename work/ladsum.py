import sys, glob, os
sys.path.insert(0, '/Users/quasarpark/meow-loop'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay, bc, ladder
from collections import Counter
def summary(path):
    ours, _ = ladder.our_team(path)
    info, out, team_of = bc.walk(path)
    them = 'B' if ours == 'A' else 'A'
    name = [l[9:] for l in info['map'].splitlines() if l.startswith('MAP_NAME')][0]
    snaps = {}; last = 0; early_feed = 0; eat = Counter()
    maxunits = 0
    for e in out:
        if e[0] == 'round':
            last = e[1]
            u = sum(1 for d, l in e[2].items() if team_of.get(d) == ours and l > 0); maxunits = max(maxunits, u)
            if e[1] in (100, 200, 300, 400, 450):
                s = {}
                for t in (ours, them):
                    ls = sorted((l for d, l in e[2].items() if team_of.get(d) == t and l > 0), reverse=True)
                    s[t] = (ls[0] if ls else 0, sum(ls), len(ls))
                snaps[e[1]] = s
        elif e[0] == 'death' and team_of.get(e[2]) == ours and e[3] == 4 and e[1] < 400:
            early_feed += 1
        elif e[0] == 'move' and e[6] > e[5] > 0 and e[1] < 100:
            eat['us' if team_of.get(e[2]) == ours else 'them'] += e[6] - e[5]
    st = info['standings']
    res = 'W' if info['winner'] == ours else 'L'
    how = '灭' if st[them]['dragons'] == 0 or st[ours]['dragons'] == 0 else '长'
    snap = '  '.join(f"r{r}:{s[ours][0]}/{s[ours][1]}/{s[ours][2]} vs {s[them][0]}/{s[them][1]}/{s[them][2]}" for r, s in sorted(snaps.items()))
    return f"{os.path.basename(path)[:-7]} {name[:13]:13s} {ours} {res}{how} r{last:3d} 终 {st[ours]['longest']:2d}/{st[ours]['total']:3d}/{st[ours]['dragons']:2d} vs {st[them]['longest']:2d}/{st[them]['total']:3d}/{st[them]['dragons']:2d} 前100吃{eat['us']}:{eat['them']} 最多单位{maxunits} 早喂{early_feed} | {snap}"
if __name__ == '__main__':
    for p in sys.argv[1:]: print(summary(p))
