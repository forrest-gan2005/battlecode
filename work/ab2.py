import os, re, sys, shutil, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'ab2')
MAP_DIRS = ['tune_runs/newmaps', 'tune_runs/official123', 'maps', 'tune_maps', 'tune_runs/variants', 'tune_runs/variants_sq', 'tune_runs/community', 'tune_runs/genmaps',
            'tune_runs/genmaps_sq', 'tune_runs/sprintmaps', 'tune_runs/genheld', 'tune_runs/genheld_sq', 'tune_runs/huge', 'tune_runs/genfresh']
RESULT = re.compile(r'team ([AB]) wins after (\d+) rounds \(([^)]*)\)')


def mp(m):
    for d in MAP_DIRS:
        p = os.path.join(ROOT, d, m + '.map')
        if os.path.exists(p):
            return p
    raise FileNotFoundError(m)


def build(tag, sets, src='mybot'):
    dst = os.path.join(ROOT, 'tune_runs', 'ab2', tag)
    src = src if os.path.isabs(src) else os.path.join(ROOT, src)
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst)
    for n in ('bot.toml', 'helper.hpp'):
        shutil.copy(os.path.join(src, n), dst)
    t = open(os.path.join(src, 'main.cpp')).read()
    for name, value in sets:
        t, n = re.subn(rf'(constexpr [\w:]+ {name} = )[^;]+;', rf'\g<1>{value};', t)
        assert n == 1, name
    open(os.path.join(dst, 'main.cpp'), 'w').write(t)
    return dst


def parse(out, ours):
    mm = RESULT.search(out)
    r = dict(win=0, us=0, them=0, rounds=500, wiped=0, wiped_them=0, how='draw')
    if mm:
        r['win'] = int(mm.group(1) == ours)
        r['rounds'] = int(mm.group(2))
        why = mm.group(3)
        nums = re.findall(r'(\d+) to (\d+)', why)
        if nums:
            w, l = int(nums[0][0]), int(nums[0][1])
            r['us'], r['them'] = (w, l) if r['win'] else (l, w)
        r['how'] = 'elim' if 'elimination' in why else 'queen' if 'queen' in why else 'longest' if 'longest' in why else 'total'
        if 'elimination' in why:
            r['wiped' if not r['win'] else 'wiped_them'] = 1
    return r, bool(mm) or 'draw' in out.lower() or 'eliminated' in out.lower()


def play(job):
    tag, bot, opp, m, seed, side = job
    a, b = (bot, opp) if side == 0 else (opp, bot)
    ours = 'A' if side == 0 else 'B'
    keep = os.environ.get('KEEP') and not os.environ.get('FAST')
    rp = os.path.join(OUT, f'{tag}_{m}_{seed}_{side}.replay')
    if keep:
        os.makedirs(OUT, exist_ok=True)
    cmd = ['unswbc', 'run', mp(m), a, b] + (['-o', rp] if keep else ['--no-replay']) + ['--no-debug']
    cmd += ([] if os.environ.get('NOSANDBOX') else ['--sandbox']) + ['--seed', str(seed)]
    out = ''
    for attempt in range(3):
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        out = proc.stdout + proc.stderr
        r, ok = parse(out, ours)
        if ok:
            return tag, m, r
    print('FAILED', tag, m, seed, side, out[-300:], file=sys.stderr, flush=True)
    return tag, m, None
