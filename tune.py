#!/usr/bin/env python3
"""自动调参：用进化策略（ES）在一组 constexpr 常量上搜索，让 bot 对一组对手打得更好。

每个候选参数都打同一批对局（相同的地图、TIE_SEED、先后手和引擎种子），分数是每局的
    胜负(1 / 0.5 / 0) + 0.5 * 最长龙相对差 + 0.25 * 总长相对差
的平均值，比只看胜负噪声小。每一代第 0 个候选是当前均值，用来看进展。

用法:
    ./tune.py                                  # 默认参数、对手 v15、10 张图各 2 局
    ./tune.py --dry-run                        # 只打印要调的参数和对局计划
    ./tune.py --opp v15 v11 --per-map 2 --gens 20 --pop 8
    ./tune.py --run myrun --resume             # 从 tune_runs/myrun 接着跑
    ./tune.py --params WEIGHT_SPACE PENALTY_HEAD_RACE   # 只调其中几个

结果写在 tune_runs/<run>/：log.jsonl（每个候选一行）、state.json（可续跑）、best.json。
跑完后用 ab.py 换一批 seed 验证最佳参数，再上传。
"""
import argparse
import concurrent.futures as cf
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import zlib

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import replay  # noqa: E402

# 名字: (类型, 下界, 上界)。初始值从 bot 的 main.cpp 里读。
SPACE = {
    'WEIGHT_SPACE': (float, 0.5, 3.0),
    'WEIGHT_TERRITORY': (float, 0.5, 3.0),
    'TARGET_REWARD': (float, 120.0, 500.0),
    'TARGET_DECAY': (float, 6.0, 30.0),
    'PENALTY_HEAD_RACE': (float, 150.0, 1200.0),
    'WEIGHT_UNSEEN': (float, 0.05, 0.6),
    'HARVEST_SEGMENT_VALUE': (float, 50.0, 300.0),
    'LEADER_GROW_ROUND': (int, 200, 400),
    'SPLIT_SOFT_LIMIT': (int, 30, 64),
    'CONTEST_SLACK': (int, 0, 3),
    'LONG_SAFE_MIN_LENGTH': (int, 5, 16),
}
DEFAULT_PARAMS = ['WEIGHT_SPACE', 'WEIGHT_TERRITORY', 'TARGET_REWARD', 'TARGET_DECAY',
                  'PENALTY_HEAD_RACE', 'LEADER_GROW_ROUND', 'SPLIT_SOFT_LIMIT', 'CONTEST_SLACK']
DEFAULT_MAPS = ['default', 'schooltime', 'trauma', 'stronghold', 'trophy', 'queen_of_spades',
                'big_empty', 'autarky', 'prisoners_dilemma', 'default_small']
EXTRA_MAPS_DIR = os.path.join(ROOT, 'tune_maps')


def read_constant(text, name):
    m = re.search(rf'constexpr [\w:]+ {name} = ([^;]+);', text)
    if not m:
        raise SystemExit(f'main.cpp 里找不到常量 {name}')
    return float(m.group(1))


def write_bot(src, dst, seed, values):
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst)
    for name in ('bot.toml', 'helper.hpp'):
        shutil.copy(os.path.join(src, name), dst)
    text = open(os.path.join(src, 'main.cpp')).read()
    text, n = re.subn(r'constexpr int TIE_SEED = \d+;', f'constexpr int TIE_SEED = {seed};', text)
    if n != 1:
        raise SystemExit(f'{src}/main.cpp 里没有 TIE_SEED')
    for name, value in values.items():
        kind = SPACE[name][0]
        literal = str(int(round(value))) if kind is int else repr(float(value))
        text, n = re.subn(rf'(constexpr [\w:]+ {name} = )[^;]+;', rf'\g<1>{literal};', text)
        if n != 1:
            raise SystemExit(f'改写 {name} 失败')
    open(os.path.join(dst, 'main.cpp'), 'w').write(text)
    return dst


def map_path(name):
    for folder in (os.path.join(ROOT, 'maps'), EXTRA_MAPS_DIR):
        path = os.path.join(folder, name + '.map')
        if os.path.exists(path):
            return path
    raise SystemExit(f'找不到地图 {name}（maps/ 或 tune_maps/）')


def standings(path):
    root = replay.load(path).root()
    result = root.pointer(4)
    out = {}
    for name, index in (('A', 0), ('B', 1)):
        side = result.pointer(index)
        out[name] = {'dragons': side.i32(0), 'longest': side.i32(4), 'total': side.i32(8)}
    winner = ('A', 'B')[result.u16(6)] if result.u16(4) == 1 else None
    return winner, out


def game_score(ours, theirs, won):
    rel = lambda a, b: (a - b) / max(1, a + b)
    return won + 0.5 * rel(ours['longest'], theirs['longest']) + 0.25 * rel(ours['total'], theirs['total'])


def play(job):
    key, mp, a, b, ours, tmp, engine_seed = job
    out_path = os.path.join(tmp, f'{key}.replay')
    cmd = ['unswbc', 'run', mp, a, b, '--sandbox', '--no-logs', '--no-indicator', '--no-draw',
           '--seed', str(engine_seed), '--output', out_path]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return key, None, 'timeout'
    if not os.path.exists(out_path):
        return key, None, (proc.stdout + proc.stderr)[-300:]
    try:
        winner, st = standings(out_path)
    finally:
        os.remove(out_path)
    theirs = 'B' if ours == 'A' else 'A'
    won = 0.5 if winner is None else float(winner == ours)
    return key, game_score(st[ours], st[theirs], won), {'won': won, 'ours': st[ours], 'theirs': st[theirs]}


class Tuner:
    def __init__(self, args):
        self.args = args
        self.dir = os.path.join(ROOT, 'tune_runs', args.run)
        self.tmp = os.path.join(self.dir, 'tmp')
        base_text = open(os.path.join(ROOT, args.bot, 'main.cpp')).read()
        self.names = args.params
        self.kinds = [SPACE[n][0] for n in self.names]
        self.low = np.array([SPACE[n][1] for n in self.names], float)
        self.high = np.array([SPACE[n][2] for n in self.names], float)
        self.initial = np.array([read_constant(base_text, n) for n in self.names], float)
        self.plan = [(opp, m, k) for opp in args.opp for m in args.maps for k in range(args.per_map)]
        self.opp_dirs = {}

    def to_values(self, x):
        v = self.low + np.clip(x, 0.0, 1.0) * (self.high - self.low)
        return {n: (int(round(val)) if kind is int else float(val)) for n, kind, val in zip(self.names, self.kinds, v)}

    def normalise(self, values):
        return (values - self.low) / (self.high - self.low)

    def opponent(self, opp, seed):
        key = (opp, seed)
        if key not in self.opp_dirs:
            self.opp_dirs[key] = write_bot(os.path.join(ROOT, opp), os.path.join(self.dir, 'bots', f'opp_{opp}_s{seed}'),
                                           seed, {})
        return self.opp_dirs[key]

    def evaluate(self, gen, candidates):
        jobs = []
        for i, x in enumerate(candidates):
            values = self.to_values(x)
            for seed in sorted({k % 5 for _, _, k in self.plan}):
                write_bot(os.path.join(ROOT, self.args.bot),
                          os.path.join(self.dir, 'bots', f'g{gen}_c{i}_s{seed}'), seed, values)
            for opp, m, k in self.plan:
                seed = k % 5
                ours_dir = os.path.join(self.dir, 'bots', f'g{gen}_c{i}_s{seed}')
                opp_dir = self.opponent(opp, seed)
                mp = map_path(m)
                key = f'g{gen}_c{i}_{opp}_{m}_{k}'
                engine_seed = zlib.crc32(f'{opp}/{m}/{k}/{self.args.engine_seed}'.encode())
                if k % 2 == 0:
                    jobs.append((key, mp, ours_dir, opp_dir, 'A', self.tmp, engine_seed))
                else:
                    jobs.append((key, mp, opp_dir, ours_dir, 'B', self.tmp, engine_seed))
        results = {}
        with cf.ThreadPoolExecutor(self.args.jobs) as pool:
            for key, score, detail in pool.map(play, jobs):
                results[key] = (score, detail)
        fitness = []
        with open(os.path.join(self.dir, 'log.jsonl'), 'a') as log:
            for i, x in enumerate(candidates):
                games = {k: v for k, v in results.items() if k.startswith(f'g{gen}_c{i}_')}
                scores = [s for s, _ in games.values() if s is not None]
                failed = [k for k, (s, _) in games.items() if s is None]
                f = float(np.mean(scores)) if scores else -1.0
                wins = sum(d['won'] for s, d in games.values() if s is not None)
                fitness.append(f)
                log.write(json.dumps({'gen': gen, 'cand': i, 'fitness': f, 'wins': wins, 'games': len(scores),
                                      'failed': failed, 'params': self.to_values(x),
                                      'per_game': {k: d for k, (s, d) in games.items()}}, ensure_ascii=False) + '\n')
        shutil.rmtree(os.path.join(self.dir, 'bots'), ignore_errors=True)
        self.opp_dirs.clear()
        return fitness

    def run(self):
        a = self.args
        os.makedirs(self.tmp, exist_ok=True)
        state_path = os.path.join(self.dir, 'state.json')
        rng = np.random.default_rng(a.rng_seed)
        if a.resume and os.path.exists(state_path):
            st = json.load(open(state_path))
            mean, sigma, gen0 = np.array(st['mean']), st['sigma'], st['gen'] + 1
            best = st.get('best')
            rng = np.random.default_rng(a.rng_seed + gen0)
            print(f'续跑：从第 {gen0} 代开始，sigma={sigma:.3f}')
        else:
            mean, sigma, gen0, best = self.normalise(self.initial), a.sigma, 0, None
        mu = max(1, a.pop // 2)
        weights = np.log(mu + 0.5) - np.log(np.arange(1, mu + 1))
        weights /= weights.sum()
        per_gen = (a.pop + 1) * len(self.plan)
        print(f'每代 {a.pop + 1} 个候选 × {len(self.plan)} 局 = {per_gen} 局')
        for gen in range(gen0, a.gens):
            started = time.time()
            half = a.pop // 2
            noise = rng.standard_normal((half, len(self.names)))
            noise = np.vstack([noise, -noise])[:a.pop]
            candidates = [mean.copy()] + [np.clip(mean + sigma * z, 0.0, 1.0) for z in noise]
            fitness = self.evaluate(gen, candidates)
            order = np.argsort(fitness[1:])[::-1]
            elite = [candidates[1 + j] for j in order[:mu]]
            new_mean = np.sum([w * e for w, e in zip(weights, elite)], axis=0)
            gen_best = int(np.argmax(fitness))
            if best is None or fitness[gen_best] > best['fitness']:
                best = {'fitness': fitness[gen_best], 'gen': gen, 'params': self.to_values(candidates[gen_best])}
                json.dump(best, open(os.path.join(self.dir, 'best.json'), 'w'), ensure_ascii=False, indent=1)
            print(f'第 {gen} 代  均值候选 {fitness[0]:.3f}  本代最好 {max(fitness):.3f}  '
                  f'历史最好 {best["fitness"]:.3f}  sigma {sigma:.3f}  用时 {time.time() - started:.0f}s')
            print('   新均值: ' + ', '.join(f'{k}={v:.4g}' for k, v in self.to_values(new_mean).items()))
            mean = new_mean
            sigma = max(a.sigma_min, sigma * a.sigma_decay)
            json.dump({'mean': mean.tolist(), 'sigma': sigma, 'gen': gen, 'best': best,
                       'names': self.names}, open(state_path, 'w'), ensure_ascii=False, indent=1)
        sets = ' '.join(f'--set L:{k}={v}' for k, v in best['params'].items())
        print(f'\n历史最好（注意：在同一批对局上挑出来的，会偏乐观）: {best}')
        print(f'验证命令（换一批 seed）: ./ab.py {a.bot} {a.opp[0]} --rshift 2 {sets}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bot', default='mybot')
    ap.add_argument('--opp', nargs='+', default=['v15'])
    ap.add_argument('--maps', nargs='+', default=DEFAULT_MAPS)
    ap.add_argument('--per-map', type=int, default=2, help='每个对手每张图打几局（seed 依次取 0..4，先后手轮换）')
    ap.add_argument('--params', nargs='+', default=DEFAULT_PARAMS, choices=sorted(SPACE))
    ap.add_argument('--pop', type=int, default=8)
    ap.add_argument('--gens', type=int, default=15)
    ap.add_argument('--sigma', type=float, default=0.15, help='初始步长（参数范围归一化到 0..1）')
    ap.add_argument('--sigma-decay', type=float, default=0.93)
    ap.add_argument('--sigma-min', type=float, default=0.04)
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--run', default=time.strftime('run_%m%d_%H%M'))
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--rng-seed', type=int, default=1)
    ap.add_argument('--engine-seed', type=int, default=0,
                    help='引擎种子的偏移：同一个值下，所有候选在同一对局位置遇到完全相同的珍珠刷新')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    tuner = Tuner(args)
    print('要调的参数（当前值 → 范围）:')
    for n, v, lo, hi in zip(tuner.names, tuner.initial, tuner.low, tuner.high):
        print(f'  {n:24s} {v:g}  [{lo:g}, {hi:g}]')
    print(f'对手 {args.opp}，地图 {len(args.maps)} 张，每候选 {len(tuner.plan)} 局；'
          f'每代 {(args.pop + 1) * len(tuner.plan)} 局，共 {args.gens} 代')
    for m in args.maps:
        map_path(m)
    for opp in args.opp:
        if not os.path.exists(os.path.join(ROOT, opp, 'main.cpp')):
            raise SystemExit(f'找不到对手 {opp}/main.cpp')
    if args.dry_run:
        return
    tuner.run()


if __name__ == '__main__':
    main()
