"""回放分析工具：逐事件重建身体、画地图。"""
import sys
from collections import deque

sys.path.insert(0, '/Users/UNSW/battlecode')
import replay

REASON = ['wall', 'self', 'body', 'head', 'suicide']


def walk(path):
    """返回 (info, 事件列表, team_of)。事件：
    ('round', r, {id: 长度}) / ('move', r, id, 旧头, 新头, 旧长, 新长)
    ('split', r, 父, 子, 父长, 子长) / ('death', r, id, 原因码, 身体)"""
    msg = replay.load(path)
    root = msg.root()
    info, _, _ = replay.parse(path)
    bodies, team_of = {}, {}
    for line in info['map'].splitlines():
        p = line.split()
        if p and p[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(p[3 + 2 * k]), int(p[4 + 2 * k])) for k in range(int(p[2])))
            team_of[did] = 'A' if int(p[1]) == 0 else 'B'
    rnd = 0
    out = []
    for ev in root.pointer(3):
        which = ev.u16(0)
        pl = ev.pointer(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else str(which)
        if kind == 'roundStart':
            rnd = pl.i32(0)
            out.append(('round', rnd, {k: len(v) for k, v in bodies.items()}))
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            head = replay.point(pl.pointer(0))
            tail = replay.point(pl.pointer(1))
            body = bodies.setdefault(did, deque())
            prev = body[0] if body else None
            before = len(body)
            if not body or body[0] != head:
                body.appendleft(head)
            while len(body) > 1 and body[-1] != tail:
                body.pop()
            out.append(('move', rnd, did, prev, head, before, len(body)))
        elif kind == 'dragonSplit':
            parent, child = pl.i32(0), pl.i32(4)
            team = ('A', 'B')[pl.u16(8)]
            bodies[parent] = deque(replay.point(p) for p in pl.pointer(0))
            bodies[child] = deque(replay.point(p) for p in pl.pointer(1))
            team_of[parent] = team_of[child] = team
            out.append(('split', rnd, parent, child, len(bodies[parent]), len(bodies[child])))
        elif kind == 'dragonDeath':
            did = pl.i32(0)
            body = bodies.pop(did, deque())
            out.append(('death', rnd, did, pl.u16(4), list(body)))
    return info, out, team_of


def load_map(text):
    lines = text.splitlines()
    W, H = map(int, lines[0].split()[1:3])
    tiles, edges = {}, {}
    for l in lines:
        p = l.split()
        if p and p[0] == 'TILE':
            x, y, a, b = map(int, p[1:])
            tiles[(x, y)] = (a, b)
        elif p and p[0] == 'EDGE':
            i, t, pid = map(int, p[1:])
            edges[i] = (t, pid)
    return W, H, tiles, edges


def edge(W, edges, x, y, side):
    row = 2 * (W + 1)
    idx = y * row + x if side == 'N' else y * row + (W + 1) + x
    return edges.get(idx, (0, -1))


def draw(text, marks=None):
    """** 泉眼(1,1)  o 快刷新  O 慢刷新  .. 不刷新；-- | 海草；P/数字 传送门。"""
    W, H, tiles, edges = load_map(text)
    marks = marks or {}
    out = []
    for y in range(H + 1):
        line = '+'
        for x in range(W):
            t, pid = edge(W, edges, x, y, 'N')
            line += ('--' if t == 1 else f'P{pid}' if t == 2 else '  ') + '+'
        out.append(line)
        if y == H:
            break
        line = ''
        for x in range(W + 1):
            t, pid = edge(W, edges, x, y, 'W')
            line += '|' if t == 1 else str(pid) if t == 2 else ' '
            if x == W:
                break
            a, b = tiles.get((x, y), (0, 0))
            cell = marks.get((x, y))
            if cell is None:
                cell = '**' if (a, b) == (1, 1) else '..' if a == 0 else 'o ' if b <= 250 else 'O '
            line += cell
        out.append(line)
    return '\n'.join(out)
