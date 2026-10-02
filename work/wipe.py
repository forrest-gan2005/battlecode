import sys, glob, os
sys.path.insert(0, '/Users/quasarpark/meow-loop'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay
from collections import Counter, deque
def ours_of(path):
    root = replay.load(path).root(); tags = Counter()
    for ev in root.pointer(3):
        if ev.u16(0) == 12:
            w = ev.pointer(0).u64(16)
            if w: tags[(w >> 53) & 3] += 1
    return 'A' if tags[2] >= tags[1] else 'B'
def run(path, upto=120):
    ours = ours_of(path)
    info, _, team_of = replay.parse(path)
    bodies = {}
    for line in info['map'].splitlines():
        p = line.split()
        if p and p[0] == 'DRAGON':
            bodies[len(bodies)] = deque((int(p[3+2*k]), int(p[4+2*k])) for k in range(int(p[2])))
    root = replay.load(path).root(); rnd = 0; mover = None; c = Counter(); corpse = {}
    for ev in root.pointer(3):
        which = ev.u16(0); pl = ev.pointer(0); kind = replay.EVENT_NAMES[which]
        if kind == 'roundStart':
            rnd = pl.i32(0)
            if rnd > upto: break
        elif kind == 'dragonAction': mover = pl.i32(0)
        elif kind == 'tileChange': pass
        elif kind == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); t = replay.point(pl.pointer(1))
            b = bodies.setdefault(did, deque()); before = len(b)
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != t: b.pop()
            if h in corpse and len(b) > before:
                src = corpse.pop(h)
                c[f"{src}尸体被{'我' if team_of.get(did) == ours else '敌'}吃"] += 1
        elif kind == 'dragonSplit':
            bodies[pl.i32(0)] = deque(replay.point(p) for p in pl.pointer(0)); bodies[pl.i32(4)] = deque(replay.point(p) for p in pl.pointer(1))
            team_of[pl.i32(0)] = team_of[pl.i32(4)] = ('A', 'B')[pl.u16(8)]
        elif kind == 'dragonDeath':
            did = pl.i32(0); r = pl.u16(4); b = bodies.pop(did, deque())
            side = '我' if team_of.get(did) == ours else '敌'
            for cell in list(b)[0::2]: corpse[cell] = side
            if r == 3:
                if mover == did: c[f'{side}主动撞头'] += 1
                else: c[f'{side}被撞头'] += 1
            else:
                c[f"{side}死:{['wall','self','body','head','none'][r]}"] += 1
    return c
if __name__ == '__main__':
    tot = Counter()
    for p in sys.argv[1:]:
        c = run(p); tot.update(c)
    for k, v in sorted(tot.items()): print(f'  {k}: {v}')
