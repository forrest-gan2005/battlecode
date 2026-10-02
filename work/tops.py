import sys, os, subprocess, gzip
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, 'tops'); os.makedirs(DIR, exist_ok=True)
DB = os.path.join(HERE, 'tops_games.tsv')
def fetch(gid):
    path = os.path.join(DIR, gid + '.replay')
    if os.path.exists(path) and os.path.getsize(path) > 0: return
    raw = subprocess.run(['curl', '-sL', f'https://game.battlecode.au/api/matches/{gid}/replay'], capture_output=True).stdout
    try: raw = gzip.decompress(raw)
    except OSError: pass
    open(path, 'wb').write(raw)
known = set()
if os.path.exists(DB):
    known = {l.split('\t')[0] for l in open(DB)}
rows = []
for line in open(sys.argv[1]):
    p = line.split()
    if len(p) < 9 or not p[0].isdigit(): continue
    sid, ta, tb, na, nb, ea, eb, ranked, games = p[:9]
    for g in games.split(','):
        gid, m, w, has = g.split(':')
        if has != '1' or gid in known: continue
        rows.append((gid, sid, m, ta, tb, na, nb, ea, eb, w))
with ThreadPoolExecutor(8) as ex: list(ex.map(fetch, [r[0] for r in rows]))
with open(DB, 'a') as f:
    for r in rows: f.write('\t'.join(r) + '\n')
print('downloaded', len(rows))
