"""Metamorphic test: does v61 play a map and its transformed copies the same way?

  python3 metamorphic.py run OUT.jsonl SEEDS SIDES MAP[,MAP...]   play v61 vs v61, keep replays

Analysis: metamorphic_stats.py. Replays go to work/ab2/mtx/ (FAST is not consulted here).

SEEDS like 1-16, SIDES like 0 or 0,1. MAP is a map id from ab2.MAP_DIRS or a .map path.
Side 0: A = tune_runs/ab2/MTX (copy of v61), B = v61; side 1 swaps them.
"""
import json, os, re, subprocess, sys, time
import concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ab2

OUT = os.path.join(ab2.OUT, 'mtx')
DRAW = re.compile(r'draw after (\d+) rounds \(([^)]*)\)')


def map_path(m):
    return m if m.endswith('.map') else ab2.mp(m)


def map_id(m):
    return os.path.splitext(os.path.basename(m))[0]


def play(job):
    m, seed, side, a, b = job
    rp = os.path.join(OUT, f'{map_id(m)}_{seed}_{side}.replay')
    a, b = (a, b) if side == 0 else (b, a)
    cmd = ['unswbc', 'run', map_path(m), a, b, '-o', rp, '--no-debug', '--seed', str(seed)]
    t = time.time()
    proc = subprocess.run(cmd, cwd=ab2.ROOT, capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    row = dict(map=map_id(m), seed=seed, side=side, replay=rp, secs=round(time.time() - t, 1),
               rc=proc.returncode, defects='defect' in out, winner=None, rounds=None, why=None)
    mm = ab2.RESULT.search(out) or DRAW.search(out)
    if mm and mm.re is ab2.RESULT:
        row.update(winner=mm.group(1), rounds=int(mm.group(2)), why=mm.group(3))
    elif mm:
        row.update(winner='draw', rounds=int(mm.group(1)), why=mm.group(2))
    else:
        row['tail'] = out[-400:]
    return row


def seeds_of(spec):
    out = []
    for part in spec.split(','):
        lo, _, hi = part.partition('-')
        out += list(range(int(lo), int(hi or lo) + 1))
    return out


def run(dst, seeds, sides, maps):
    os.makedirs(OUT, exist_ok=True)
    a = ab2.build('MTX', [], 'v61')
    b = os.path.join(ab2.ROOT, 'v61')
    for bot in (a, b):  # compile once before the pool starts
        subprocess.run(['unswbc', 'run', os.path.join(ab2.ROOT, 'tune_runs/official127/arena.map'), bot, bot,
                        '--no-replay', '--no-debug', '--seed', '1'], cwd=ab2.ROOT, capture_output=True)
    jobs = [(m, s, side, a, b) for m in maps for s in seeds for side in sides]
    workers = min(6, int(os.environ.get('WORKERS', '6')))
    t = time.time()
    with open(dst, 'a') as f, cf.ProcessPoolExecutor(workers) as pool:
        for k, row in enumerate(pool.map(play, jobs)):
            f.write(json.dumps(row) + '\n')
            f.flush()
            if row['winner'] is None or row['defects'] or row['rc']:
                print('PROBLEM', row, file=sys.stderr, flush=True)
            if (k + 1) % 20 == 0:
                print(f'{k + 1}/{len(jobs)} games, {time.time() - t:.0f}s', flush=True)
    print(f'done {len(jobs)} games in {time.time() - t:.0f}s', flush=True)


if __name__ == '__main__':
    if len(sys.argv) >= 6 and sys.argv[1] == 'run':
        run(sys.argv[2], seeds_of(sys.argv[3]), seeds_of(sys.argv[4]), sys.argv[5].split(','))
    else:
        print(__doc__)
        sys.exit(2)
