"""Write transformed copies of a map (transpose, rotations, mirrors).

The board is a torus: the north edge of row 0 is also the south edge of row H-1,
and the west edge of column 0 is the east edge of column W-1. Edge index layout:
row = 2*(W+1); north edge of (x,y) = y*row + x; west edge = y*row + (W+1) + x.
Portals keep their ids; both edges of a pair move together. Generated maps that repeat
the east/south border (x = W, y = H) are read if the copies match; output is canonical.

usage:
  python3 maptx.py MAP T1[,T2...] [OUT_DIR] [--suffix S]   write OUT_DIR/<stem>_<T or S>.map
  python3 maptx.py --show MAP [T]             ASCII render (optionally after T)
  python3 maptx.py --selftest [MAP...]        round trips + independent cell/edge check
"""
import os, re, string, sys

# Transforms act on centred coordinates u = 2x-(W-1), v = 2y-(H-1): (u,v) -> M(u,v).
T = {
    'identity': ((1, 0), (0, 1)),
    'transpose': ((0, 1), (1, 0)),
    'rot90': ((0, -1), (1, 0)),      # clockwise on screen (y grows south)
    'rot180': ((-1, 0), (0, -1)),
    'rot270': ((0, 1), (-1, 0)),
    'mirror_x': ((-1, 0), (0, 1)),   # x -> W-1-x
    'mirror_y': ((1, 0), (0, -1)),   # y -> H-1-y
    'antitranspose': ((0, -1), (-1, 0)),
}
NAME = {m: n for n, m in T.items()}
# SYMMETRY header -> the map's own symmetry: y = mirror in x, x = mirror in y, xy = rot180.
SYM = {'y': T['mirror_x'], 'x': T['mirror_y'], 'xy': T['rot180']}
SYM_NAME = {m: n for n, m in SYM.items()}


def mul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(2)) for j in range(2)) for i in range(2))


def inv(m):
    return next(n for n in T.values() if mul(n, m) == T['identity'])


def parse(text):
    m = dict(sym=None, name='', tiles={}, north={}, west={}, dragons=[], end=False)
    copies = []
    for line in text.splitlines():
        p = line.split()
        if not p:
            continue
        k = p[0]
        if k == 'MAP':
            m['W'], m['H'] = int(p[1]), int(p[2])
        elif k == 'SYMMETRY':
            m['sym'] = p[1]
        elif k == 'MAP_NAME':
            m['name'] = line.split(None, 1)[1] if len(p) > 1 else ''
        elif k == 'TILE':
            x, y, a, b = map(int, p[1:5])
            m['tiles'][(x, y)] = (a, b)
        elif k == 'EDGE':
            i, t, pid = map(int, p[1:4])
            W, H = m['W'], m['H']
            y, r = divmod(i, 2 * (W + 1))
            side, x = ('north', r) if r <= W else ('west', r - W - 1)
            if x < W and y < H:
                m[side][(x, y)] = (t, pid)
            elif side == 'north' and x == W and y <= H and t == 0:
                pass  # no tile at x = W: an open placeholder
            elif (side == 'west' and x == W and y < H) or (side == 'north' and x < W and y == H):
                copies.append((side, x % W, y % H, (t, pid), line))  # east / south border repeated
            else:
                raise ValueError('edge outside the torus layout: ' + line)
        elif k == 'DRAGON':
            n = int(p[2])
            m['dragons'].append((int(p[1]), [(int(p[3 + 2 * j]), int(p[4 + 2 * j])) for j in range(n)]))
        elif k == 'END':
            m['end'] = True
        elif k not in ('TILE_COUNT', 'EDGE_COUNT', 'DRAGON_COUNT'):
            raise ValueError('unknown map line: ' + line)
    for side, x, y, v, line in copies:
        if m[side].get((x, y), (0, -1)) != v:
            raise ValueError('border edge differs from the edge it wraps to: ' + line)
    return m


def dump(m):
    W, H = m['W'], m['H']
    row = 2 * (W + 1)
    out = [f'MAP {W} {H}']
    if m['sym']:
        out.append(f"SYMMETRY {m['sym']}")
    out.append(f"MAP_NAME {m['name']}")
    out.append(f"TILE_COUNT {len(m['tiles'])}")
    out += [f'TILE {x} {y} %d %d' % m['tiles'][(x, y)] for y in range(H) for x in range(W) if (x, y) in m['tiles']]
    out.append(f"EDGE_COUNT {len(m['north']) + len(m['west'])}")
    for y in range(H):
        out += [f'EDGE {y * row + x} %d %d' % m['north'][(x, y)] for x in range(W) if (x, y) in m['north']]
        out += [f'EDGE {y * row + W + 1 + x} %d %d' % m['west'][(x, y)] for x in range(W) if (x, y) in m['west']]
    out.append(f"DRAGON_COUNT {len(m['dragons'])}")
    out += ['DRAGON %d %d ' % (t, len(cells)) + ' '.join(f'{x} {y}' for x, y in cells) for t, cells in m['dragons']]
    if m['end']:
        out.append('END')
    return '\n'.join(out) + '\n'


def size(mat, W, H):
    return (H, W) if mat[0][0] == 0 else (W, H)


def point(mat, W, H, x, y):
    W2, H2 = size(mat, W, H)
    u, v = 2 * x - (W - 1), 2 * y - (H - 1)
    u2, v2 = mat[0][0] * u + mat[0][1] * v, mat[1][0] * u + mat[1][1] * v
    return (u2 + W2 - 1) // 2, (v2 + H2 - 1) // 2


def between(a, b, W, H):
    """('N'|'W', cell) naming the edge between torus-adjacent cells a and b."""
    if a[0] == b[0]:
        return ('N', b) if (a[1] + 1) % H == b[1] else ('N', a)
    return ('W', b) if (a[0] + 1) % W == b[0] else ('W', a)


def split_name(name):
    mm = re.fullmatch(r'(.*) \((\w+)\)', name)
    if mm and mm.group(2) in T:
        return mm.group(1), T[mm.group(2)]
    return name, T['identity']


def apply(m, tname):
    mat = T[tname]
    W, H = m['W'], m['H']
    assert W >= 3 and H >= 3
    W2, H2 = size(mat, W, H)
    f = lambda c: point(mat, W, H, *c)
    n = dict(W=W2, H=H2, end=m['end'], tiles={}, north={}, west={})
    for c, v in m['tiles'].items():
        n['tiles'][f(c)] = v
    for kind, edges in (('N', m['north']), ('W', m['west'])):
        for (x, y), v in edges.items():
            a = (x, (y - 1) % H) if kind == 'N' else ((x - 1) % W, y)
            side, cell = between(f(a), f((x, y)), W2, H2)
            n['north' if side == 'N' else 'west'][cell] = v
    n['dragons'] = [(t, [f(c) for c in cells]) for t, cells in m['dragons']]
    n['sym'] = SYM_NAME[mul(mul(mat, SYM[m['sym']]), inv(mat))] if m['sym'] else None
    base, prev = split_name(m['name'])
    net = mul(mat, prev)
    n['name'] = base if net == T['identity'] else f'{base} ({NAME[net]})'
    return n


def edge_of(m, a, b):
    side, cell = between(a, b, m['W'], m['H'])
    return (m['north'] if side == 'N' else m['west']).get(cell, (0, -1))


def symmetries(m):
    """SYMMETRY labels whose mirror/rotation maps tiles, kelp and portal pairs onto themselves."""
    W, H = m['W'], m['H']
    ok = []
    for label, mat in SYM.items():
        if size(mat, W, H) != (W, H):
            continue
        s = apply(dict(m, sym=None), NAME[mat])
        if s['tiles'] != m['tiles']:
            continue
        types = lambda e: {c: v[0] for c, v in e.items()}
        if types(s['north']) != types(m['north']) or types(s['west']) != types(m['west']):
            continue
        ids = {}
        for e0, e1 in ((m['north'], s['north']), (m['west'], s['west'])):
            for c, (t, pid) in e0.items():
                if t == 2:
                    ids.setdefault(pid, set()).add(e1[c][1])
        if all(len(v) == 1 for v in ids.values()):
            ok.append(label)
    return ok


def check_pair(m, n, tname):
    """Independent check of n == tname(m): every cell, every edge (as a cell pair), every dragon."""
    mat = T[tname]
    W, H = m['W'], m['H']
    f = lambda c: point(mat, W, H, *c)
    assert (n['W'], n['H']) == size(mat, W, H)
    assert [len(n[k]) for k in ('tiles', 'north', 'west')] == [len(m[k]) for k in ('tiles', 'north', 'west')]
    for c, v in m['tiles'].items():
        assert n['tiles'][f(c)] == v, (c, f(c))
    for y in range(H):
        for x in range(W):
            for d in ((1, 0), (0, 1)):
                b = ((x + d[0]) % W, (y + d[1]) % H)
                assert edge_of(n, f((x, y)), f(b)) == edge_of(m, (x, y), b), ((x, y), b)
    assert [(t, [f(c) for c in cells]) for t, cells in m['dragons']] == n['dragons']
    pairs = {}
    for side in ('north', 'west'):
        for c, (t, pid) in n[side].items():
            if t == 2:
                pairs.setdefault(pid, []).append(side)
    assert all(len(v) == 2 and v[0] == v[1] for v in pairs.values()), pairs
    for t, cells in n['dragons']:
        for a, b in zip(cells, cells[1:]):
            dx, dy = (a[0] - b[0]) % n['W'], (a[1] - b[1]) % n['H']
            assert (dx in (1, n['W'] - 1) and dy == 0) or (dy in (1, n['H'] - 1) and dx == 0), (a, b)


def render(m):
    """** spring  o fast  O slow  .. none; -- | kelp; Pk / k portal (k = 0-9a-zA-Z); Q/q queen head,
    A/B other heads, a/b bodies. The last row and column repeat the first ones (torus wrap)."""
    W, H = m['W'], m['H']
    key = lambda pid: (string.digits + string.ascii_letters)[pid] if pid < 62 else '?'
    marks = {}
    for i, (t, cells) in enumerate(m['dragons']):
        for j, c in enumerate(cells):
            marks[c] = ('Qq'[t] if i < 2 else 'AB'[t]) + ' ' if j == 0 else 'ab'[t] + ' '
    out = []
    for y in range(H + 1):
        line = '+'
        for x in range(W):
            t, pid = m['north'].get((x, y % H), (0, -1))
            line += ('--' if t == 1 else 'P' + key(pid) if t == 2 else '  ') + '+'
        out.append(line)
        if y == H:
            break
        line = ''
        for x in range(W + 1):
            t, pid = m['west'].get((x % W, y), (0, -1))
            line += '|' if t == 1 else key(pid) if t == 2 else ' '
            if x == W:
                break
            a, b = m['tiles'].get((x, y), (0, 0))
            line += marks.get((x, y), '**' if (a, b) == (1, 1) else '..' if a == 0 else 'o ' if b <= 250 else 'O ')
        out.append(line)
    return '\n'.join(out)


def selftest(paths):
    for p in paths:
        text = open(p).read()
        m = parse(text)
        dropped = text.count('\nEDGE ') - len(m['north']) - len(m['west'])
        if dropped:
            text = dump(m)
            assert parse(text) == m, p + ': canonical form does not read back'
            print(f'canonicalised {os.path.basename(p)}: {dropped} border edge lines dropped')
        assert dump(m) == text, p + ': not canonical'
        assert m['sym'] in symmetries(m), (p, m['sym'], symmetries(m))
        for t in T:
            n = apply(m, t)
            check_pair(m, n, t)
            assert n['sym'] in symmetries(n), (p, t, n['sym'])
            assert apply(n, NAME[inv(T[t])]) == m, (p, t)
        for t, k in (('rot90', 4), ('rot270', 4), ('transpose', 2), ('mirror_x', 2), ('mirror_y', 2), ('rot180', 2)):
            x = text
            for _ in range(k):
                x = dump(apply(parse(x), t))
            assert x == text, (p, t, k)
        print('ok', os.path.basename(p), m['W'], m['H'], 'sym', m['sym'], 'holds', symmetries(m))


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '--selftest':
        selftest(a[1:])
    elif a and a[0] == '--show':
        m = parse(open(a[1]).read())
        print(render(apply(m, a[2]) if len(a) > 2 else m))
    elif len(a) >= 2:
        suffix = a.pop(a.index('--suffix') + 1) if '--suffix' in a else None
        a = [x for x in a if x != '--suffix']
        src = a[0]
        out = a[2] if len(a) > 2 else os.path.dirname(os.path.abspath(src))
        os.makedirs(out, exist_ok=True)
        m = parse(open(src).read())
        stem = os.path.splitext(os.path.basename(src))[0]
        assert not suffix or ',' not in a[1], '--suffix takes one transform'
        for t in a[1].split(','):
            dst = os.path.join(out, f'{stem}_{suffix or t}.map')
            open(dst, 'w').write(dump(apply(m, t)))
            print(dst)
    else:
        print(__doc__)
        sys.exit(2)
