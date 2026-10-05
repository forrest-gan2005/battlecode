#!/usr/bin/env python3
"""QUEEN_STRIDE mechanism check from kept ab replays (work/ab2/{TAG}_{map}_{seed}_{side}.replay).

usage: python3 qsmech.py TAG [TAG ...] [--dir work/ab2]

Our side is A for side 0 and B for side 1. For each tag: our queen alive at the end,
death rounds and reasons, our queen length at r50/r100/r200/r300 while alive, queen sprints
(moves of 2+ steps) and sprints taken with an enemy head within 4, plus their queen for reference.
"""
import glob, os, statistics, sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import qwatch2

REASONS = ['wall', 'self', 'body', 'head', 'none']


def one(path):
    base = os.path.basename(path)[:-7]
    tag, rest = base.split('_', 1)
    side = int(rest.rsplit('_', 1)[1])
    ours = 'A' if side == 0 else 'B'
    g = qwatch2.track(path)
    st = g['stats'][ours]
    th = g['stats']['B' if ours == 'A' else 'A']
    near = [n <= 4 for n in st['near']]
    return dict(tag=tag, map=g['map'], cells=g['cells'], win=g['winner'] == ours, end=g['end'],
                qlen=g['qlen'][ours], their_qlen=g['qlen']['B' if ours == 'A' else 'A'],
                death=st['death'], their_death=th['death'], lens={r: st['len'].get(r) for r in (50, 100, 200, 300)},
                sprints=st['sprints'], splits=len(st['splits']), alive_rounds=len(st['near']),
                near_rounds=sum(near), danger=len(st['danger']))


def main():
    args = sys.argv[1:]
    d = os.path.join(HERE, 'ab2')
    if '--dir' in args:
        i = args.index('--dir'); d = args[i + 1]; del args[i:i + 2]
    files = [f for t in args for f in glob.glob(os.path.join(d, f'{t}_*.replay'))]
    with ProcessPoolExecutor(4) as ex:
        rows = list(ex.map(one, files))
    by = defaultdict(list)
    for r in rows:
        by[r['tag']].append(r)
    for tag in args:
        rs = by.get(tag, [])
        if not rs:
            continue
        big = [r for r in rs if r['cells'] > 600]
        for label, sub in (('all', rs), ('>600', big)):
            if not sub:
                continue
            n = len(sub)
            alive = sum(1 for r in sub if r['death'] is None)
            deaths = [r['death'] for r in sub if r['death']]
            why = Counter(REASONS[x[1]] if isinstance(x[1], int) and x[1] < 5 else x[1] for x in deaths)
            med = statistics.median([x[0] for x in deaths]) if deaths else None
            lens = {k: [r['lens'][k] for r in sub if r['lens'][k]] for k in (50, 100, 200, 300)}
            lstr = ' '.join(f"r{k}:{len(v)}/{statistics.mean(v):.1f}" if v else f"r{k}:0" for k, v in lens.items())
            qrounds = sum(r['alive_rounds'] for r in sub)
            print(f"{tag:5s} {label:4s} games {n:3d} wins {sum(r['win'] for r in sub):3d} | our queen alive {alive:3d} "
                  f"median death r{med} {dict(why)} | alive/mean len {lstr} | sprints {sum(r['sprints'] for r in sub)} "
                  f"| queen-rounds {qrounds} enemy<=4 {sum(r['near_rounds'] for r in sub)} danger {sum(r['danger'] for r in sub)} "
                  f"| their queen alive {sum(1 for r in sub if r['their_death'] is None)}")


if __name__ == '__main__':
    main()
