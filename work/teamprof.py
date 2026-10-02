import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, '/Users/UNSW/battlecode')
import replay, ourside
from collections import deque, Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
CK = [50, 100, 200, 300, 400, 499]
def run(job):
    p, side, team = job
    try:
        info, _, team_of = replay.parse(p)
    except Exception:
        return None
    bodies = {}
    for line in info['map'].splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies); bodies[did] = deque((int(q[3+2*k]), int(q[4+2*k])) for k in range(int(q[2]))); team_of.setdefault(did, 'A' if int(q[1]) == 0 else 'B')
    mine = lambda d: team_of.get(d) == side
    c = Counter(); rnd = 0; actor = None; upd = 0; first20 = None
    for ev in replay.load(p).root().pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]; pl = ev.pointer(0)
        if k == 'roundStart':
            rnd = pl.i32(0)
            if rnd in CK:
                mb = [len(b) for d, b in bodies.items() if b and mine(d)]
                c['u%d' % rnd] += len(mb); c['t%d' % rnd] += sum(mb); c['top%d' % rnd] += max(mb) if mb else 0
            if first20 is None:
                mb = [len(b) for d, b in bodies.items() if b and mine(d)]
                if mb and max(mb) >= 20: first20 = rnd
        elif k == 'turnStart': actor = pl.i32(0); upd = 0
        elif k == 'dragonUpdate':
            did = pl.i32(0); h = replay.point(pl.pointer(0)); tp = replay.point(pl.pointer(1)); b = bodies.setdefault(did, deque()); before = len(b)
            if did == actor: upd += 1
            if not b or b[0] != h: b.appendleft(h)
            while len(b) > 1 and b[-1] != tp: b.pop()
            if len(b) > before and mine(did):
                c['eat100' if rnd < 100 else 'eat300' if rnd < 300 else 'eat500'] += len(b) - before
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0)); bodies[ch] = deque(replay.point(x) for x in pl.pointer(1)); team_of[pa] = team_of[ch] = ('A','B')[pl.u16(8)]
            if mine(pa): c['split%s' % ('100' if rnd < 100 else '300' if rnd < 300 else '500')] += 1
        elif k == 'dragonDeath':
            did = pl.i32(0); r = pl.u16(4); b = bodies.pop(did, deque())
            if r == 3 and actor is not None and actor != did and mine(actor) and not mine(did):
                c['ram'] += 1; c['ramsprint'] += upd >= 1
            if not mine(did): continue
            ph = '100' if rnd < 100 else '300' if rnd < 300 else '500'
            c['death' + ph] += 1
            if r == 4: c['sui' + ('300' if rnd < 300 else '400' if rnd < 400 else '500')] += 1
            if r in (0, 1): c['trap' + ph] += 1
    win = (info['winner'] or '') == side
    c['win'] += win; c['n'] += 1
    c['first20'] += first20 if first20 is not None else 500
    end = info['standings'][side]
    c['endtop'] += end['longest']; c['endtot'] += end['total']
    c['wiped'] += end['dragons'] == 0
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
    want = sys.argv[1:] or ['Cutlery', 'forgot_to_mention', '3.14159265', 'SSS', 'cheji_bt', 'Cache_me_outside', 'calc', 'Stockfish', 'PPP', 'C--(v52)']
    print('%-18s %3s %4s | %-22s | %-22s | %-22s | %-22s | eat100 eat300 | split100/300 | death100/300 trap300 | sui<300 300-400 400+ | ram(sprint) | top20@ | end top/tot wiped' % ('team', 'n', 'win', 'r100 u/tot/top', 'r200', 'r300', 'r400'))
    for t in want:
        c = T.get(t)
        if not c or not c['n']: continue
        n = c['n']; g = lambda k: c[k] / n
        cell = lambda r: '%4.1f/%5.1f/%4.1f' % (g('u%d' % r), g('t%d' % r), g('top%d' % r))
        print('%-18s %3d %3.0f%% | %-22s | %-22s | %-22s | %-22s | %5.1f %6.1f | %5.1f/%5.1f | %5.1f/%5.1f %5.1f | %4.1f %4.1f %4.1f | %4.1f(%4.1f) | %5.0f | %4.1f/%5.1f %3.0f%%' % (
            t[:18], n, 100 * g('win'), cell(100), cell(200), cell(300), cell(400), g('eat100'), g('eat300'), g('split100'), g('split300'),
            g('death100'), g('death300'), g('trap300'), g('sui300'), g('sui400'), g('sui500'), g('ram'), g('ramsprint'), g('first20'), g('endtop'), g('endtot'), 100 * g('wiped')))
