#!/usr/bin/env python3
"""并行 A/B：每张图 × 每个 TIE_SEED（只有 0-4 五个不同取值）× 先后手各一局。

用法:
  ab.py LEFT RIGHT [--maps a b c] [--seeds 5] [--jobs 6] [--set L:NAME=VALUE ...] [--tag x]
LEFT/RIGHT 是项目里的 bot 目录；--set 在复制出来的 L 或 R 里改 constexpr 常量。
"""
import argparse
import concurrent.futures as cf
import os
import re
import shutil
import subprocess
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
HERE = os.path.join(ROOT, 'tune_runs', 'ab')
EXTRA_MAPS = {'autarky': os.path.join(ROOT, 'tune_maps', 'autarky.map'),
              'prisoners_dilemma': os.path.join(ROOT, 'tune_maps', 'prisoners_dilemma.map'),
              'portals': os.path.join(ROOT, 'tune_maps', 'portals.map'),
              'slithery_fight': os.path.join(ROOT, 'tune_maps', 'slithery_fight.map')}
DEFAULT_MAPS = ['autarky', 'default', 'devil', 'portals', 'prisoners_dilemma', 'queen_of_spades',
                'schooltime', 'slithery_fight', 'trauma', 'trophy']


def build(src, tag, seed, sets):
    dst = os.path.join(HERE, 'seeds', f'{tag}_s{seed}')
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst)
    for name in os.listdir(src):
        if name != 'main.cpp' and (name == 'bot.toml' or name.endswith(('.hpp', '.h', '.cpp', '.cc', '.hh'))):
            shutil.copy(os.path.join(src, name), dst)
    text = open(os.path.join(src, 'main.cpp')).read()
    text = re.sub(r'constexpr int TIE_SEED = \d+;', f'constexpr int TIE_SEED = {seed};', text)
    for name, value in sets:
        text, n = re.subn(rf'(constexpr [\w:]+ {name} = )[^;]+;', rf'\g<1>{value};', text)
        assert n == 1, name
    open(os.path.join(dst, 'main.cpp'), 'w').write(text)
    return dst


def play(game):
    mp, a, b, left_is_a, key = game
    out = subprocess.run(['unswbc', 'run', mp, a, b, '--sandbox', '--no-replay'], cwd=ROOT, capture_output=True, text=True).stdout
    line = next((l for l in out.splitlines() if 'wins' in l or 'draw' in l), '')
    if not line:
        return key, None, out[-300:]
    if 'draw' in line:
        return key, 0.5, line
    return key, 1.0 if ('team A wins' in line) == left_is_a else 0.0, line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('left')
    ap.add_argument('right')
    ap.add_argument('--maps', nargs='+', default=DEFAULT_MAPS)
    ap.add_argument('--seeds', type=int, default=5)
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--set', action='append', default=[])
    ap.add_argument('--tag', default='')
    ap.add_argument('--rshift', type=int, default=0, help='右边用 (seed + rshift) % 5，换一批对局')
    ap.add_argument('--per-map', type=int, default=5,
                    help='每张图只打这么多局：seed 依次取 0,1,2..（模 5），先后手轮流；0 表示每个 seed 先后手各一局')
    args = ap.parse_args()

    sets = {'L': [], 'R': []}
    for item in args.set:
        side, rest = item.split(':', 1)
        name, value = rest.split('=', 1)
        sets[side].append((name, value))
    ltag = args.tag + 'L_' + os.path.basename(args.left.rstrip('/'))
    rtag = args.tag + 'R_' + os.path.basename(args.right.rstrip('/')) + (f'_x{args.rshift}' if args.rshift else '')

    games = []
    if args.per_map:
        built = {}
        for k in range(args.per_map):
            seed = k % 5
            if seed not in built:
                built[seed] = (build(os.path.join(ROOT, args.left), ltag, seed, sets['L']),
                               build(os.path.join(ROOT, args.right), rtag, (seed + args.rshift) % 5, sets['R']))
            lp, rp = built[seed]
            for m in args.maps:
                mp = EXTRA_MAPS.get(m, os.path.join(ROOT, 'maps', m + '.map'))
                if k % 2 == 0:
                    games.append((mp, lp, rp, True, m))
                else:
                    games.append((mp, rp, lp, False, m))
    for seed in range(0 if args.per_map else args.seeds):
        lp = build(os.path.join(ROOT, args.left), ltag, seed, sets['L'])
        rp = build(os.path.join(ROOT, args.right), rtag, (seed + args.rshift) % 5, sets['R'])
        for m in args.maps:
            mp = EXTRA_MAPS.get(m, os.path.join(ROOT, 'maps', m + '.map'))
            games.append((mp, lp, rp, True, m))
            games.append((mp, rp, lp, False, m))

    score = defaultdict(float)
    count = defaultdict(int)
    wiped = defaultdict(int)
    wiped_them = defaultdict(int)
    errors = []
    with cf.ThreadPoolExecutor(args.jobs) as pool:
        for key, pts, line in pool.map(play, games):
            if pts is None:
                errors.append((key, line))
                continue
            score[key] += pts
            count[key] += 1
            if 'elimination' in line:
                (wiped if pts == 0.0 else wiped_them)[key] += 1
    total = 0.0
    for m in args.maps:
        total += score[m]
        print(f'{m:18s} {score[m]:4.1f} : {count[m] - score[m]:4.1f}   全灭 {wiped_them[m]} : {wiped[m]}')
    n = sum(count.values())
    print(f'{"合计":16s} {total:4.1f} : {n - total:4.1f}   全灭 {sum(wiped_them.values())} : {sum(wiped.values())}   ({args.left} {sets["L"]} vs {args.right} {sets["R"]}, {n} 局)')
    for key, line in errors[:5]:
        print('未出结果:', key, line.replace('\n', ' | '))


if __name__ == '__main__':
    main()
