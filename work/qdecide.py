#!/usr/bin/env python3
"""Queen decisions under threat, from replays (queens = dragons 0 and 1).

usage: python3 qdecide.py REPLAY... [--ours A|B] [--show N]

For every queen action it rebuilds the board at the moment she acts and records:
nearest enemy head (BFS through free cells), whether her chosen cell is inside some
visible enemy's one-action kill reach (enemy length L reaches L-1 steps), whether a
safe single step existed, sprint length, splits, and the distance change.
Loop rounds use #40's counter: at most 4 distinct head cells in the last 12 rounds.
"""
import os, sys
from collections import defaultdict, deque, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import replay
from qwatch2 import Board, DIRS


def bfs_free(board, start, blocked, cap):
    dist = {start: 0}
    q = deque([start])
    while q:
        c = q.popleft()
        if dist[c] >= cap:
            continue
        for n in board.open_nbrs(c):
            if n in dist or n in blocked:
                continue
            dist[n] = dist[c] + 1
            q.append(n)
    return dist


def analyse(path, show=0, ours='A'):
    info, _, _ = replay.parse(path)
    board = Board(info['map'])
    bodies, team_of = {}, {}
    for line in info['map'].splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
    queens = {0, 1}
    out = {team_of[q]: dict(q=q, acts=0, exposed=0, exposed_safe_alt=0, nearacts=0, away=0, closer=0, same=0,
                            sprint_escape=0, sprint_total=0, split_near=0, loops=0, alive_rounds=0,
                            deaths=None, examples=[], hist=deque(maxlen=12), stay_near=0, safe_alt_none=0)
           for q in queens}
    rnd = 0
    cur = None
    pre = None
    steps = 0

    def threats(team, head):
        occ = set()
        for d, b in bodies.items():
            occ.update(b)
        res = []
        for d, b in bodies.items():
            if not b or team_of[d] == team:
                continue
            L = len(b)
            reach = max(1, L - 1)
            dist = bfs_free(board, b[0], occ - {head}, min(reach, 8))
            res.append((d, b[0], L, reach, dist))
        return res, occ

    def in_reach(cell, ths):
        for d, e, L, reach, dist in ths:
            if cell in dist and dist[cell] <= reach:
                return (d, L, dist[cell])
        return None

    def finish():
        nonlocal cur, pre
        if cur is None or pre is None:
            cur = None
            return
        q = cur
        t = team_of[q]
        st = out[t]
        if q not in bodies:
            cur = None
            return
        head = bodies[q][0]
        ths, occ = pre['ths'], pre['occ']
        hit = in_reach(head, ths) if pre['kind'] == 'move' else in_reach(pre['head'], ths)
        st['acts'] += 1
        if hit:
            st['exposed'] += 1
            if pre['safe_alt']:
                st['exposed_safe_alt'] += 1
                if len(st['examples']) < show:
                    st['examples'].append((rnd, pre['head'], head, pre['kind'], steps, hit, pre['len']))
            else:
                st['safe_alt_none'] += 1
        if pre['near'] <= 3:
            st['nearacts'] += 1
            after = min((board.man(head, e) for _, e, *_ in ths), default=99)
            if after > pre['nearman']:
                st['away'] += 1
            elif after < pre['nearman']:
                st['closer'] += 1
            else:
                st['same'] += 1
            if steps >= 2:
                st['sprint_escape'] += 1
            if pre['kind'] == 'split':
                st['split_near'] += 1
        if steps >= 2:
            st['sprint_total'] += 1
        cur = None

    root = replay.load(path).root()
    for ev in root.pointer(3):
        k = replay.EVENT_NAMES[ev.u16(0)]
        pl = ev.pointer(0)
        if k == 'roundStart':
            finish()
            rnd = pl.i32(0)
            for q in queens:
                if q in bodies and team_of.get(q) in out:
                    st = out[team_of[q]]
                    st['alive_rounds'] += 1
                    st['hist'].append(bodies[q][0])
                    if len(st['hist']) == 12 and len(set(st['hist'])) <= 4:
                        st['loops'] += 1
        elif k == 'dragonAction':
            finish()
            did = pl.i32(0)
            a = pl.pointer(0)
            if did in queens and did in bodies:
                t = team_of[did]
                head = bodies[did][0]
                ths, occ = threats(t, head)
                kind = 'move' if a and a.u16(0) == 0 else 'split' if a and a.u16(0) == 1 else 'other'
                own = set(bodies[did])
                safe_alt = False
                for n in board.open_nbrs(head):
                    if n in occ and n != bodies[did][-1]:
                        continue
                    if n == bodies[did][-1] and len(bodies[did]) > 1:
                        continue
                    if not in_reach(n, ths):
                        safe_alt = True
                        break
                near = min((dist.get(head, 99) for *_, dist in ths), default=99)
                nearman = min((board.man(head, e) for _, e, *_ in ths), default=99)
                pre = dict(head=head, ths=ths, occ=occ, kind=kind, safe_alt=safe_alt, near=near, nearman=nearman,
                           len=len(bodies[did]))
                cur = did
                steps = 0
        elif k == 'dragonUpdate':
            did = pl.i32(0)
            h = replay.point(pl.pointer(0))
            tl = replay.point(pl.pointer(1))
            b = bodies.setdefault(did, deque())
            if b and b[0] != h and did == cur:
                steps += 1
            if not b or b[0] != h:
                b.appendleft(h)
            while len(b) > 1 and b[-1] != tl:
                b.pop()
        elif k == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            team = ('A', 'B')[pl.u16(8)]
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0))
            bodies[ch] = deque(replay.point(x) for x in pl.pointer(1))
            team_of[pa] = team_of[ch] = team
        elif k == 'dragonDeath':
            did = pl.i32(0)
            if did == cur:
                finish()
            bodies.pop(did, None)
            if did in queens:
                out[team_of[did]]['deaths'] = (rnd, pl.u16(4))
    finish()
    return board.name, out


if __name__ == '__main__':
    args = sys.argv[1:]
    ours = 'A'
    show = 0
    if '--ours' in args:
        i = args.index('--ours'); ours = args[i + 1]; del args[i:i + 2]
    if '--show' in args:
        i = args.index('--show'); show = int(args[i + 1]); del args[i:i + 2]
    tot = {s: Counter() for s in ('us', 'them')}
    for p in args:
        name, out = analyse(p, show, ours)
        for side, t in (('us', ours), ('them', 'B' if ours == 'A' else 'A')):
            st = out[t]
            for key in ('acts', 'exposed', 'exposed_safe_alt', 'safe_alt_none', 'nearacts', 'away', 'closer', 'same',
                        'sprint_escape', 'sprint_total', 'split_near', 'loops', 'alive_rounds'):
                tot[side][key] += st[key]
            print(f"{name[:14]:14s} {side:4s} acts {st['acts']:3d} exposed {st['exposed']:2d} (safe alt {st['exposed_safe_alt']:2d}, none {st['safe_alt_none']:2d}) "
                  f"| near<=3 acts {st['nearacts']:3d}: away {st['away']:3d} closer {st['closer']:3d} same {st['same']:3d} sprint {st['sprint_escape']:3d} split {st['split_near']:2d} "
                  f"| sprints {st['sprint_total']:3d} loops {st['loops']:3d}/{st['alive_rounds']} death {st['deaths']}")
            for ex in st['examples']:
                print('      exposed with safe alt:', ex)
    for side in ('us', 'them'):
        c = tot[side]
        kr = c['alive_rounds'] / 1000
        print(f"TOTAL {side}: queen-rounds {c['alive_rounds']} exposed {c['exposed']} ({c['exposed'] / kr:.1f}/1000) voluntary {c['exposed_safe_alt']} ({c['exposed_safe_alt'] / kr:.1f}/1000) "
              f"forced {c['safe_alt_none']} | near<=3 {c['nearacts']}: away {c['away']} closer {c['closer']} same {c['same']} sprint {c['sprint_escape']} split {c['split_near']} "
              f"| loop rounds {c['loops']} ({100 * c['loops'] / max(1, c['alive_rounds']):.1f}%)")
