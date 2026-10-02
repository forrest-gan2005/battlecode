import sys, os, subprocess, hashlib
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay
ROOT = '/Users/quasarpark/meow-loop'
REF = os.environ.get('REF', 'v53')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ident')
os.makedirs(OUT, exist_ok=True)
MAPS = [('maps/default.map', 100), ('maps/trauma.map', 101), ('maps/queen_of_spades.map', 102), ('maps/schooltime.map', 103),
        ('tune_runs/variants/portals_v0.map', 104), ('tune_runs/variants/slithery_fight_v0.map', 105),
        ('tune_runs/variants/autarky_v0.map', 106), ('tune_runs/variants/devil_v0.map', 107),
        ('tune_runs/variants/prisoners_dilemma_v0.map', 108), ('maps/trophy.map', 109)]
def digest(p):
    h = hashlib.sha1()
    for ev in replay.load(p).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'dragonUpdate': h.update(f"u{pl.i32(0)}{replay.point(pl.pointer(0))}{replay.point(pl.pointer(1))}".encode())
        elif k == 'dragonDeath': h.update(f"d{pl.i32(0)}{pl.u16(4)}".encode())
        elif k == 'dragonSplit': h.update(f"s{pl.i32(0)}{pl.i32(4)}".encode())
        elif k == 'roundStart': h.update(f"r{pl.i32(0)}".encode())
    return h.hexdigest()
def play(job):
    tag, a, b, m, s = job
    out = os.path.join(OUT, f"{tag}_{os.path.basename(m)[:-4]}_{s}.replay")
    if not os.path.exists(out):
        subprocess.run(['unswbc', 'run', os.path.join(ROOT, m), os.path.join(ROOT, a), os.path.join(ROOT, b), '--sandbox', '--seed', str(s), '-o', out], capture_output=True)
    return job, digest(out)
if __name__ == '__main__':
    cand = sys.argv[1]
    tag = os.path.basename(cand.rstrip('/'))
    for f in os.listdir(OUT):
        if f.startswith(tag + 'A_') or f.startswith(tag + 'B_'): os.remove(os.path.join(OUT, f))
    jobs = []
    for m, s in MAPS:
        jobs.append(('ref' + REF, REF, REF, m, s))
        jobs.append((tag + 'A', cand, REF, m, s))
        jobs.append((tag + 'B', REF, cand, m, s))
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(play, jobs))
    ref = {(j[3], j[4]): d for j, d in res if j[0] == 'ref' + REF}
    bad = 0
    for j, d in res:
        if j[0] == 'ref' + REF: continue
        ok = d == ref[(j[3], j[4])]
        bad += not ok
        print(('OK  ' if ok else 'DIFF'), j[0], os.path.basename(j[3]))
    print('identical' if bad == 0 else f'{bad} differ')
