import sys, os, glob, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import replay
from collections import deque, Counter
from concurrent.futures import ProcessPoolExecutor

CAUSE = ['wall', 'self', 'body', 'headon', 'none']


def one(path):
    ours = 'A' if path.endswith('_0.replay') else 'B'
    info, _, team_of = replay.parse(path)
    lines = info['map'].splitlines()
    W, H = map(int, lines[0].split()[1:3])
    bodies = {}
    for line in lines:
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
    c = Counter()
    rnd = 0
    for ev in replay.load(path).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]
        pl = ev.pointer(0)
        if k == 'roundStart':
            rnd = pl.i32(0)
            if rnd == 300:
                c['total300'] = sum(len(b) for d, b in bodies.items() if b and team_of.get(d) == ours)
                c['units300'] = sum(1 for d, b in bodies.items() if b and team_of.get(d) == ours)
        elif k == 'dragonAction':
            mover = pl.i32(0)
            a = pl.pointer(0)
            if team_of.get(mover) != ours or a is None or a.u16(0) != 0:
                continue
            L = len(bodies.get(mover, ()))
            if L < 5:
                continue
            try:
                n = len(a.pointer(0))
            except Exception:
                n = 1
            c['moves5'] += 1
            c['multi5'] += n >= 2
            c['steps5'] += n
        elif k == 'dragonUpdate':
            did = pl.i32(0)
            h = replay.point(pl.pointer(0))
            tp = replay.point(pl.pointer(1))
            b = bodies.setdefault(did, deque())
            before = len(b)
            if not b or b[0] != h:
                b.appendleft(h)
            while len(b) > 1 and b[-1] != tp:
                b.pop()
            if team_of.get(did) == ours and before > 0 and len(b) > before:
                c['eats'] += 1
                if 100 <= rnd < 300:
                    c['eats100_300'] += 1
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0))
            bodies[ch] = deque(replay.point(x) for x in pl.pointer(1))
            team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
        elif k == 'dragonDeath':
            did = pl.i32(0)
            r = pl.u16(4)
            b = bodies.pop(did, None)
            if team_of.get(did) != ours or not b:
                continue
            cause = CAUSE[r] if r < 5 else str(r)
            if rnd < 300 and cause in ('wall', 'self', 'body'):
                c['selfdeath300'] += 1
            if rnd < 300 and len(b) >= 5:
                c['death5_300'] += 1
    c['games'] = 1
    c['big'] = W * H > 1200
    return c


if __name__ == '__main__':
    out_dir = sys.argv[1]
    for tag in sys.argv[2].split(','):
        files = glob.glob(os.path.join(out_dir, f'{tag}_*.replay'))
        with ProcessPoolExecutor(6) as ex:
            rs = list(ex.map(one, files))
        for label, keep in (('big >1200', lambda r: r['big']), ('all', lambda r: True)):
            s = Counter()
            for r in rs:
                if keep(r):
                    s.update(r)
            g = max(1, s['games'])
            m = max(1, s['moves5'])
            print(f"{tag:7s} {label:10s} games {s['games']:3d} | L>=5 multi-step {100 * s['multi5'] / m:5.1f}% mean steps {s['steps5'] / m:.2f} | "
                  f"eats/game {s['eats'] / g:6.1f} r100-300 {s['eats100_300'] / g:6.1f} | total r300 {s['total300'] / g:6.1f} units r300 {s['units300'] / g:5.1f} | "
                  f"self-deaths<300 {s['selfdeath300'] / g:5.1f} L>=5 deaths<300 {s['death5_300'] / g:5.1f}")
