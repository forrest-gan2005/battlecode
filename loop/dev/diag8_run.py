import os, sys, subprocess, concurrent.futures as cf
sys.path.insert(0, '/Users/quasarpark/meow-loop/work')
import ab2
D = '/Users/quasarpark/meow-loop/loop/dev'
opp = os.path.join(ab2.ROOT, 'v61')
bot = os.path.join(ab2.ROOT, 'tune_runs', 'ab2', 'DIAG8')
def one(job):
    m, seed, side = job
    log = f'{D}/diag8_logs/{m}_{seed}_{side}.log'
    if os.path.exists(log): os.remove(log)
    a, b = (bot, opp) if side == 0 else (opp, bot)
    env = dict(os.environ, DIAG8=log)
    p = subprocess.run(['unswbc', 'run', ab2.mp(m), a, b, '--no-replay', '--no-debug', '--seed', str(seed)], cwd=ab2.ROOT, env=env, capture_output=True, text=True)
    r, ok = ab2.parse(p.stdout + p.stderr, 'A' if side == 0 else 'B')
    return m, seed, side, r
if __name__ == '__main__':
  ab2.build('DIAG8', [], os.path.join(D, 'diag8'))
  maps = sys.argv[1].split(',')
  os.makedirs(f'{D}/diag8_logs', exist_ok=True)
  jobs = [(m, 7000 + k, k % 2) for m in maps for k in range(2)]
  with cf.ProcessPoolExecutor(8) as ex:
    for res in ex.map(one, jobs): print(*res, flush=True)
