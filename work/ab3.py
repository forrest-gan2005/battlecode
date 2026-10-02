import sys, os, json, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ab2
from collections import defaultdict


def summary(rows, tags):
    by = defaultdict(dict)
    for r in rows:
        by[r['tag']][(r['map'], r['seed'], r['side'])] = r
    base = tags[0]
    for tag in tags:
        rs = list(by[tag].values())
        if not rs:
            continue
        n = len(rs)
        w = sum(r['win'] for r in rs)
        us = sum(r['us'] for r in rs) / n
        th = sum(r['them'] for r in rs) / n
        plus = minus = 0
        for k, r in by[tag].items():
            b = by[base].get(k)
            if b:
                plus += r['win'] and not b['win']
                minus += b['win'] and not r['win']
        print(f'{tag:6s} 胜 {w:2d}/{n}  长 {us:.1f}:{th:.1f}  相对{base}: +{plus} -{minus}', flush=True)


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
    workers = int(os.environ.get('WORKERS', '8'))
    if os.environ.get('DIST'):
        import distq
        keep = os.environ.get('KEEP') and not os.environ.get('FAST')
        rp = (lambda job: os.path.join(ab2.OUT, f'{job[0]}_{job[3]}_{job[4]}_{job[5]}.replay')) if keep else None
        results = distq.run(jobs, ab2.play, ab2.mp, workers, rp)
        for job, r in zip(jobs, results):
            if r is None:
                continue
            rows.append(dict(tag=job[0], map=job[3], seed=job[4], side=job[5], **r))
    else:
        with cf.ProcessPoolExecutor(workers) as pool:
            for job, (tag, m, r) in zip(jobs, pool.map(ab2.play, jobs)):
                if r is None:
                    continue
                rows.append(dict(tag=tag, map=m, seed=job[4], side=job[5], **r))
    json.dump(rows, open(out, 'w'))
    summary(rows, [t for t, _ in configs])
