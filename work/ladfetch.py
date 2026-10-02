import sys, os, subprocess, gzip
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, 'nr'); os.makedirs(DIR, exist_ok=True)
def fetch(gid):
    path = os.path.join(DIR, gid + '.replay')
    if os.path.exists(path) and os.path.getsize(path) > 0: return
    raw = subprocess.run(['curl', '-sL', f'https://game.battlecode.au/api/matches/{gid}/replay'], capture_output=True).stdout
    try: raw = gzip.decompress(raw)
    except OSError: pass
    open(path, 'wb').write(raw)
ids = []
for line in open(sys.argv[1]):
    p = line.split()
    if len(p) < 6: continue
    for g in p[5].split(','):
        gid, m, w, has = g.split(':')
        if has == '1': ids.append(gid)
with ThreadPoolExecutor(8) as ex: list(ex.map(fetch, ids))
print('have', len(ids))
