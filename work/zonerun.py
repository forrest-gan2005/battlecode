#!/usr/bin/env python3
"""Run kept-replay games with bot logs for mechanism checks (ab3 drops logs with --no-debug).

usage: python3 zonerun.py MAPS OPP N OUTDIR TAG@src:TOGGLE=v,... [...]
Replays go to OUTDIR/<tag>_<map>_<seed>_<side>.replay. Env: WORKERS (4), SEED0 (100), NOSANDBOX.
"""
import os, subprocess, sys, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ab2


def play(job):
    tag, bot, opp, m, seed, side, out = job
    rp = os.path.join(out, f'{tag}_{m}_{seed}_{side}.replay')
    if os.path.exists(rp):
        return rp
    a, b = (bot, opp) if side == 0 else (opp, bot)
    cmd = ['unswbc', 'run', ab2.mp(m), a, b, '-o', rp, '--seed', str(seed)]
    cmd += [] if os.environ.get('NOSANDBOX') else ['--sandbox']
    subprocess.run(cmd, cwd=ab2.ROOT, capture_output=True, text=True)
    return rp


if __name__ == '__main__':
    maps = sys.argv[1].split(',')
    opp = os.path.join(ab2.ROOT, sys.argv[2])
    n = int(sys.argv[3])
    out = os.path.abspath(sys.argv[4])
    os.makedirs(out, exist_ok=True)
    configs = []
    for spec in sys.argv[5:]:
        tag, _, rest = spec.partition(':')
        src = 'mybot2'
        if '@' in tag:
            tag, src = tag.split('@')
        configs.append((tag, ab2.build(tag, [tuple(kv.split('=')) for kv in rest.split(',') if kv], src)))
    seed0 = int(os.environ.get('SEED0', '100'))
    jobs = [(tag, bot, opp, m, seed0 + k // 2, k % 2, out) for m in maps for k in range(n) for tag, bot in configs]
    with cf.ProcessPoolExecutor(int(os.environ.get('WORKERS', '4'))) as pool:
        for k, rp in enumerate(pool.map(play, jobs)):
            if (k + 1) % 20 == 0:
                print(f'{k + 1}/{len(jobs)}', flush=True)
    print('done', len(jobs))
