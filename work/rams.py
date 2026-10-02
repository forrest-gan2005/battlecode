import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, '/Users/quasarpark/meow-loop')
import replay, ourside
from collections import deque, Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
def run(job):
    p, side, team = job
    try: info, _, team_of = replay.parse(p)
    except Exception: return None
    bodies = {}
    for line in info['map'].splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    mine = lambda d: team_of.get(d) == side
    c = Counter(); rnd = 0; actor = None; upd = 0; startlen = {}
    pend = None
    for ev in replay.load(p).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart': rnd = pl.i32(0)
        elif k == 'turnStart':
            actor = pl.i32(0); upd = 0; startlen[actor] = len(bodies.get(actor, ()))
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque())
            if did == actor: upd += 1
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A','B')[pl.u16(8)]
        elif k == 'dragonDeath':
            did = pl.i32(0); r = pl.u16(4); b = bodies.pop(did, deque())
            if r != 3 or actor is None or actor == did: continue
            if mine(actor) and not mine(did):
                ph = 'early' if rnd < 300 else 'late'
                c['ram_' + ph] += 1; c['ram_sprint_' + ph] += upd >= 1
                c['rammer_len_' + ph] += startlen.get(actor, 0); c['victim_len_' + ph] += len(b)
                c['big_victim'] += len(b) >= 10
    c['n'] += 1
    return team, c
if __name__ == '__main__':
    jobs = []
    for l in open('tops_games.tsv'):
        r = l.rstrip('\n').split('\t')
        jobs.append(('tops/%s.replay' % r[0], 'A', r[5])); jobs.append(('tops/%s.replay' % r[0], 'B', r[6]))
    for f in sorted(glob.glob('v52all/*.replay')):
        jobs.append((f, ourside.ours_of(f), 'C--(v52)'))
    T = defaultdict(Counter)
    with ProcessPoolExecutor(6) as ex:
        for res in ex.map(run, jobs, chunksize=4):
            if res: T[res[0]].update(res[1])
    for t in ['Cutlery', 'forgot_to_mention', '3.14159265', 'SSS', 'cheji_bt', 'Cache_me_outside', 'calc', 'Stockfish', 'C--(v52)']:
        c = T[t]; n = c['n']
        if not n: continue
        out = []
        for ph in ('early', 'late'):
            k = max(1, c['ram_' + ph])
            out.append('%s: %.1f/g sprint %.0f%% rammer L %.1f victim L %.1f' % (ph, c['ram_' + ph] / n, 100 * c['ram_sprint_' + ph] / k, c['rammer_len_' + ph] / k, c['victim_len_' + ph] / k))
        print('%-18s %s | big victims (L>=10) %.2f/g' % (t, ' | '.join(out), c['big_victim'] / n))
