import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bc
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
TOP = {'Cache_me_outside', 'Stockfish', '3.14159265', 'calc', 'Sponge(Albert_and_Bob)', 'Team_SKKU', 'Computers', 'horse', 'WeHaveQuizzes'}
def one(a):
    f, ours, mp = a
    info, out, team_of = bc.walk(f)
    l0 = info['map'].splitlines()[0].split(); W, H = int(l0[1]), int(l0[2])
    first = {}; cnt = defaultdict(int); qfirst = {}
    for e in out:
        if e[1] > 150: break
        if e[0] == 'move' and e[3] and e[4]:
            dx = min(abs(e[3][0] - e[4][0]), W - abs(e[3][0] - e[4][0])); dy = min(abs(e[3][1] - e[4][1]), H - abs(e[3][1] - e[4][1]))
            if dx + dy > 1 and dx + dy > 6:
                t = 'us' if team_of.get(e[2]) == ours else 'them'
                first.setdefault(t, e[1])
                if e[2] in (0, 1): qfirst.setdefault(t, e[1])
                if e[1] <= 100: cnt[t] += 1
    return mp, first.get('us', 999), first.get('them', 999), cnt['us'], cnt['them'], qfirst.get('us', 999), qfirst.get('them', 999)
if __name__ == '__main__':
    args = []
    if sys.argv[1] == 'local':
        for f in sorted(glob.glob(f'ab2/{sys.argv[2]}_*.replay')):
            p = os.path.basename(f)[:-7].split('_'); args.append((f, 'A' if p[-1] == '0' else 'B', '_'.join(p[1:-2])))
    else:
        for line in open(sys.argv[1]):
            p = line.split()
            if len(p) < 6 or p[2] not in TOP: continue
            for g in p[5].split(','):
                gid, mp, res, has = g.split(':')
                if os.path.exists(f'nr/{gid}.replay'): args.append((f'nr/{gid}.replay', p[4], mp))
    with ProcessPoolExecutor(6) as ex: rows = list(ex.map(one, args))
    by = defaultdict(list)
    for r in rows: by[r[0]].append(r)
    for mp, rs in sorted(by.items()):
        n = len(rs); med = lambda i: sorted(r[i] for r in rs)[n // 2]
        print(f"{mp:16s} n{n:2d} first portal use median {med(1)}|{med(2)}  queen {med(5)}|{med(6)}  portal jumps r0-100 {sum(r[3] for r in rs)/n:.1f}|{sum(r[4] for r in rs)/n:.1f}")
