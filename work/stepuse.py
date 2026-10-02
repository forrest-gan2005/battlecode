import sys, os
sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay
from collections import deque, Counter, defaultdict
def run(f, side):
    info, _, team_of = replay.parse(f)
    lines = info['map'].splitlines()
    bodies = {}
    for l in lines:
        q = l.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    c = Counter(); actor = None; upd = 0; alen = 0; rnd = 0
    def close():
        if actor is not None and upd > 0 and team_of.get(actor) == side:
            f_ = (alen + 3) // 4
            c['turns'] += 1; c['steps'] += upd
            c['multi'] += upd > 1
            if f_ >= 2:
                c['cap_turns'] += 1; c['cap_multi'] += upd > 1; c['cap_steps'] += upd; c['cap_free'] += f_
                c['paid'] += max(0, upd - f_)
    for ev in replay.load(f).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart': rnd = pl.i32(0)
        elif k == 'turnStart':
            close(); actor = pl.i32(0); upd = 0; alen = len(bodies.get(actor, ()))
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            if did == actor: upd += 1
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4); bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A','B')[pl.u16(8)]
        elif k == 'dragonDeath': bodies.pop(pl.i32(0), None)
    close()
    return c
if __name__ == '__main__':
    agg = defaultdict(Counter)
    for l in open(sys.argv[1]):
        p = l.split(); team, tid, a, b = p[0], p[1], p[3], p[4]
        side = 'A' if a == tid else 'B'
        for g in p[7].split(','):
            gid = g.split(':')[0]
            try: agg[team].update(run(f'{sys.argv[2]}/{gid}.replay', side))
            except Exception as e: print('ERR', gid, e)
    for t, c in agg.items():
        print('%-11s turns %6d steps/turn %.2f multi %.1f%% | when ceil(L/4)>=2: turns %6d steps/turn %.2f multi %.1f%% free avail %.2f paid steps %d' % (t, c['turns'], c['steps']/max(1,c['turns']), 100*c['multi']/max(1,c['turns']), c['cap_turns'], c['cap_steps']/max(1,c['cap_turns']), 100*c['cap_multi']/max(1,c['cap_turns']), c['cap_free']/max(1,c['cap_turns']), c['paid']))
