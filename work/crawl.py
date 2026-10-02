import sys, os, subprocess, gzip
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, '/Users/quasarpark/meow-loop')
import ladsum
DIR = os.path.join(HERE, 'crawl'); os.makedirs(DIR, exist_ok=True)
DB = os.path.join(HERE, 'crawl_games.tsv')
LOG = os.path.join(HERE, 'crawl_log.txt')

def fetch(gid):
    path = os.path.join(DIR, gid + '.replay')
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        raw = subprocess.run(['curl', '-sL', f'https://game.battlecode.au/api/matches/{gid}/replay'], capture_output=True).stdout
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
        open(path, 'wb').write(raw)
    try:
        return gid, ladsum.summary(path)
    except Exception as e:
        return gid, f'{gid} parse error {e}'

def main(listfile):
    known = {}
    if os.path.exists(DB):
        for line in open(DB):
            q = line.rstrip('\n').split('\t')
            known[q[0]] = q
    new_rows = []; todo = []
    for line in open(listfile):
        q = line.split()
        if len(q) < 7: continue
        bid, ranked, status, opp, oelo, side, games = q[:7]
        for g in games.split(','):
            gid, mp, res, has = g.split(':')
            if res not in ('W', 'L', 'D') or has != '1' or gid in known: continue
            row = [gid, bid, ranked, opp, oelo, mp, res]
            new_rows.append(row); todo.append(gid)
    summ = {}
    with ProcessPoolExecutor(6) as ex:
        for gid, s in ex.map(fetch, todo): summ[gid] = s
    with open(DB, 'a') as f:
        for row in new_rows: f.write('\t'.join(row) + '\n'); known[row[0]] = row
    out = []
    byb = defaultdict(list)
    for row in new_rows: byb[(row[1], row[2], row[3], row[4])].append(row)
    out.append(f'新增 {len(new_rows)} 局（{len(byb)} 场对战）')
    for (bid, ranked, opp, oelo), rows in byb.items():
        w = sum(r[6] == 'W' for r in rows); l = sum(r[6] == 'L' for r in rows)
        out.append(f"  {bid} {'排位' if ranked == 'R' else '友谊'} vs {opp}({oelo}) {w}:{l}  " + ' '.join(f"{r[5]}{r[6]}" for r in rows))
        for r in rows:
            if r[6] == 'L': out.append('     输 ' + summ.get(r[0], ''))
    agg = defaultdict(lambda: [0, 0]); aggR = defaultdict(lambda: [0, 0])
    for row in known.values():
        a = agg[row[5]]; a[0 if row[6] == 'W' else 1] += 1
        if row[2] == 'R':
            b = aggR[row[5]]; b[0 if row[6] == 'W' else 1] += 1
    out.append('累计分图胜负（全部 / 仅排位）:')
    for mp in sorted(agg, key=lambda m: agg[m][0] / max(1, sum(agg[m]))):
        a = agg[mp]; b = aggR[mp]
        out.append(f"  {mp:18s} {a[0]:3d}:{a[1]:<3d} {100*a[0]/max(1,sum(a)):3.0f}%   排位 {b[0]}:{b[1]}")
    text = '\n'.join(out)
    with open(LOG, 'a') as f:
        f.write(subprocess.run(['date'], capture_output=True, text=True).stdout + text + '\n\n')
    print(text)

if __name__ == '__main__':
    main(sys.argv[1])
