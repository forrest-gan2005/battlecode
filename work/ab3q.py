#!/usr/bin/env python3
"""ab3.py with queen fates: the same jobs and summary, plus each queen's death round and cause from the engine output.

usage: same as ab3.py (MAPS OPP N OUT.json TAG@src:TOGGLE=v,...). Rows gain qdeath/qcause (ours) and edeath (theirs).
"""
import os, re, subprocess, sys, json, concurrent.futures as cf
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ab2, ab3

DEATH = re.compile(r'round (\d+): bot ([01]) \(team ([AB])\) died: ([^\n]+)')


def play(job):
    tag, bot, opp, m, seed, side = job
    a, b = (bot, opp) if side == 0 else (opp, bot)
    ours = 'A' if side == 0 else 'B'
    keep = os.environ.get('KEEP') and not os.environ.get('FAST')
    rp = os.path.join(ab2.OUT, f'{tag}_{m}_{seed}_{side}.replay')
    if keep:
        os.makedirs(ab2.OUT, exist_ok=True)
    cmd = ['unswbc', 'run', ab2.mp(m), a, b] + (['-o', rp] if keep else ['--no-replay']) + ['--no-debug']
    cmd += ([] if os.environ.get('NOSANDBOX') else ['--sandbox']) + ['--seed', str(seed)]
    for attempt in range(3):
        proc = subprocess.run(cmd, cwd=ab2.ROOT, capture_output=True, text=True)
        out = proc.stdout + proc.stderr
        r, ok = ab2.parse(out, ours)
        if ok:
            r['qdeath'] = r['edeath'] = None
            r['qcause'] = ''
            for rnd, bid, team, cause in DEATH.findall(out):
                if team == ours and r['qdeath'] is None:
                    r['qdeath'], r['qcause'] = int(rnd), cause.strip()
                elif team != ours and r['edeath'] is None:
                    r['edeath'] = int(rnd)
            return tag, m, r
    print('FAILED', tag, m, seed, side, out[-300:], file=sys.stderr, flush=True)
    return tag, m, None


def queen_summary(rows, tags):
    by = defaultdict(dict)
    for r in rows:
        by[r['tag']][(r['map'], r['seed'], r['side'])] = r
    base = tags[0]
    for tag in tags:
        rs = list(by[tag].values())
        if not rs:
            continue
        alive = sum(r['qdeath'] is None for r in rs)
        early = sum(r['qdeath'] is not None and r['qdeath'] < 300 for r in rs)
        qwin = sum(r['win'] and r['how'] == 'queen' for r in rs)
        qloss = sum(not r['win'] and r['how'] == 'queen' for r in rs)
        ealive = sum(r['edeath'] is None for r in rs)
        qp = qm = 0
        for k, r in by[tag].items():
            b = by[base].get(k)
            if b:
                qp += r['qdeath'] is None and b['qdeath'] is not None
                qm += r['qdeath'] is not None and b['qdeath'] is None
        print(f'{tag:6s} queen alive {alive}/{len(rs)} (vs {base}: +{qp} -{qm})  dead<r300 {early}  queen-decided W{qwin} L{qloss}  enemy queen alive {ealive}', flush=True)


if __name__ == '__main__':
    maps = sys.argv[1].split(',')
    opp = os.path.join(ab2.ROOT, sys.argv[2])
    n = int(sys.argv[3])
    out = sys.argv[4]
    configs = []
    for spec in sys.argv[5:]:
        tag, _, rest = spec.partition(':')
        src = 'mybot'
        if '@' in tag:
            tag, src = tag.split('@')
        configs.append((tag, ab2.build(tag, [tuple(kv.split('=')) for kv in rest.split(',') if kv], src)))
    seed0 = int(os.environ.get('SEED0', '100'))
    jobs = [(tag, bot, opp, m, seed0 + k // 2, k % 2) for m in maps for k in range(n) for tag, bot in configs]
    rows = []
    with cf.ProcessPoolExecutor(int(os.environ.get('WORKERS', '8'))) as pool:
        for job, (tag, m, r) in zip(jobs, pool.map(play, jobs)):
            if r is None:
                continue
            rows.append(dict(tag=tag, map=m, seed=job[4], side=job[5], **r))
    json.dump(rows, open(out, 'w'))
    tags = [t for t, _ in configs]
    ab3.summary(rows, tags)
    queen_summary(rows, tags)
