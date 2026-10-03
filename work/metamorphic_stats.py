"""Metrics and comparisons for metamorphic.py runs (a map vs transformed copies of it).

  python3 metamorphic_stats.py MAIN.jsonl [--side SIDE.jsonl] [--extra EXTRA.jsonl] [--out OUT.md]

Per game: how it ended, length, total length per side at r100/r300, units at r100, queen
death rounds, self-inflicted deaths (wall/self/body) before r200, head distance to the
centre at r30/r60, portal jumps. Every head move is also checked against the original map
(mapped back through the inverse transform): steps must not cross kelp or portals, jumps
must land where the original portal pair sends them.
"""
import hashlib, json, math, os, random, re, statistics, sys
import concurrent.futures as cf
from collections import Counter, defaultdict, deque
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import maptx, replay

TX = ('transpose', 'rot90', 'mirror_x', 'rot180', 'rot270', 'mirror_y')
MAIN_TX = ('transpose', 'rot90', 'mirror_x')
SNAP = (30, 60, 100, 200, 300)
STEP = ((0, -1), (1, 0), (0, 1), (-1, 0))  # N E S W
SELF = (0, 1, 2)  # wall, self, body
MECH = ('cdist30', 'cdist60', 'east60', 'north60', 'jumps')
METRICS = [
    ('rounds', 'game length'), ('elim', 'ended by elimination'), ('A_win', 'team A won'),
    ('tot100_A', 'total len A r100'), ('tot100_B', 'total len B r100'),
    ('tot300_A', 'total len A r300'), ('tot300_B', 'total len B r300'),
    ('units100_A', 'units A r100'), ('units100_B', 'units B r100'),
    ('qdied_A', 'queen A died'), ('qdied_B', 'queen B died'),
    ('qround_A', 'queen A death round (end if alive)'), ('qround_B', 'queen B death round (end if alive)'),
    ('qlen_A', 'queen A length at end'), ('qlen_B', 'queen B length at end'),
    ('self200_A', 'self deaths A <r200'), ('self200_B', 'self deaths B <r200'),
    ('cdist30', 'head-centre dist r30 (norm)'), ('cdist60', 'head-centre dist r60 (norm)'),
    ('east60', 'E share of E/W steps r<60 (orig frame)'), ('north60', 'N share of N/S steps r<60 (orig frame)'),
    ('jumps', 'portal jumps'),
]


def split_id(mid):
    for t in TX:
        if mid.endswith('_' + t):
            return mid[:-len(t) - 1], t
    return mid, 'identity'


@lru_cache(None)
def original(base):
    return partners(open(os.path.join(ROOT, 'tune_runs/official127', base + '.map')).read())


@lru_cache(None)
def partners(text):
    """(parsed map, {portal edge: partner edge}) with edges as ('N'|'W', cell)."""
    m = maptx.parse(text)
    pid = defaultdict(list)
    for side, key in (('N', 'north'), ('W', 'west')):
        for c, (t, p) in m[key].items():
            if t == 2:
                pid[p].append((side, c))
    out = {}
    for es in pid.values():
        out[es[0]], out[es[1]] = es[1], es[0]
    return m, out


def classify(m, part, a, b):
    """'step', 'jump', or a violation: 'kelp' / 'portal' (plain step across one), 'odd' (no rule fits)."""
    W, H = m['W'], m['H']
    blocked = 'odd'
    for k, (dx, dy) in enumerate(STEP):
        nb = ((a[0] + dx) % W, (a[1] + dy) % H)
        side, cell = maptx.between(a, nb, W, H)
        t, _ = (m['north'] if side == 'N' else m['west']).get(cell, (0, -1))
        if t == 0 and nb == b:
            return 'step'
        if t == 2:
            s2, c2 = part[(side, cell)]
            if s2 == 'N':
                land = {0: (c2[0], (c2[1] - 1) % H), 2: c2}.get(k)
            else:
                land = {3: ((c2[0] - 1) % W, c2[1]), 1: c2}.get(k)
            if land == b:
                return 'jump'
        if nb == b:
            blocked = 'kelp' if t == 1 else 'portal'
    return blocked


def walk(path):
    root = replay.load(path).root()
    text = root.text(0)
    res = root.pointer(4)
    final = {s: dict(dragons=res.pointer(i).i32(0), total=res.pointer(i).i32(8)) for i, s in enumerate('AB')}
    bodies, team = {}, {}
    for line in text.splitlines():
        p = line.split()
        if p and p[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(p[3 + 2 * k]), int(p[4 + 2 * k])) for k in range(int(p[2])))
            team[did] = 'AB'[int(p[1])]
    snaps, deaths, moves = {}, [], []
    digest = hashlib.sha1()
    rnd = 0
    for ev in root.pointer(3):
        kind = ev.u16(0)
        pl = ev.pointer(0)
        if kind == 0:
            rnd = pl.i32(0)
            if rnd in SNAP:
                snaps[rnd] = [(team[d], len(b), b[0]) for d, b in bodies.items()]
        elif kind == 9:
            did = pl.i32(0)
            head, tail = replay.point(pl.pointer(0)), replay.point(pl.pointer(1))
            body = bodies.setdefault(did, deque())
            if body and body[0] != head:
                moves.append((rnd, body[0], head))
            if not body or body[0] != head:
                body.appendleft(head)
            while len(body) > 1 and body[-1] != tail:
                body.pop()
            digest.update(repr((rnd, did, head, tail)).encode())
        elif kind == 10:
            parent, child = pl.i32(0), pl.i32(4)
            bodies[parent] = deque(replay.point(p) for p in pl.pointer(0))
            bodies[child] = deque(replay.point(p) for p in pl.pointer(1))
            team[parent] = team[child] = 'AB'[pl.u16(8)]
            digest.update(repr((rnd, 's', parent, child)).encode())
        elif kind == 11:
            did = pl.i32(0)
            body = bodies.pop(did, deque())
            deaths.append((rnd, did, team.get(did), pl.u16(4), len(body)))
            digest.update(repr((rnd, 'd', did)).encode())
    alive = {d: len(b) for d, b in bodies.items()}
    return dict(text=text, final=final, elim=res.u16(2) == 0, snaps=snaps, deaths=deaths, moves=moves,
                alive=alive, digest=digest.hexdigest())


def how(why):
    for key, name in (('both teams', 'elim-both'), ('elimination', 'elim'), ('queen', 'queen'),
                      ('longest', 'longest'), ('total', 'total'), ('equal', 'draw')):
        if why and key in why:
            return name
    return '?'


def analyse(row):
    g = walk(row['replay'])
    base, t = split_id(row['map'])
    m, part = partners(g['text'])
    W, H = m['W'], m['H']
    o, opart = original(base)
    back = maptx.inv(maptx.T[t])
    here, there, own, orig = Counter(), Counter(), Counter(), Counter()
    for rnd, a, b in g['moves']:
        kind = classify(m, part, a, b)
        here[kind] += 1
        a0, b0 = maptx.point(back, W, H, *a), maptx.point(back, W, H, *b)
        there[classify(o, opart, a0, b0)] += 1
        if kind == 'step' and rnd < 60:
            own[compass(a, b, W, H)] += 1
            orig[compass(a0, b0, o['W'], o['H'])] += 1
    x = dict(rounds=row['rounds'], elim=int(g['elim']),
             A_win={'A': 1.0, 'B': 0.0}.get(row['winner'], 0.5), jumps=here['jump'],
             east60=orig['E'] / max(1, orig['E'] + orig['W']), north60=orig['N'] / max(1, orig['N'] + orig['S']))
    for r in (100, 300):
        for s in 'AB':
            snap = g['snaps'].get(r)
            x[f'tot{r}_{s}'] = sum(n for tm, n, _ in snap if tm == s) if snap else g['final'][s]['total']
            if r == 100:
                x[f'units{r}_{s}'] = sum(1 for tm, _, _ in snap if tm == s) if snap else g['final'][s]['dragons']
    dead = {did: rnd for rnd, did, _, _, _ in g['deaths'] if did in (0, 1)}
    for did, s in ((0, 'A'), (1, 'B')):
        x[f'qdied_{s}'] = int(did in dead)
        x[f'qround_{s}'] = dead.get(did, row['rounds'])
        x[f'qlen_{s}'] = g['alive'].get(did, 0)
        x[f'self200_{s}'] = sum(1 for rnd, _, tm, why, _ in g['deaths'] if tm == s and rnd < 200 and why in SELF)
    cx, cy = (W - 1) / 2, (H - 1) / 2
    for r in (30, 60):
        snap = g['snaps'].get(r)
        d = [min(abs(p[0] - cx), W - abs(p[0] - cx)) + min(abs(p[1] - cy), H - abs(p[1] - cy)) for _, _, p in snap or []]
        x[f'cdist{r}'] = statistics.mean(d) / ((W + H) / 4) if d else None
    return dict(row, base=base, tx=t, how=how(row['why']), m=x, here=dict(here), there=dict(there), own=dict(own),
                digest=g['digest'])


def compass(a, b, W, H):
    dx, dy = (b[0] - a[0]) % W, (b[1] - a[1]) % H
    return 'E' if dx == 1 else 'W' if dx == W - 1 else 'S' if dy == 1 else 'N'


def perm_p(a, b, n=20000, rng=random.Random(7)):
    obs = abs(statistics.mean(b) - statistics.mean(a))
    pool, k, tot = a + b, len(a), sum(a) + sum(b)
    if obs == 0:
        return 1.0
    hit = 0
    for _ in range(n):
        s = sum(rng.sample(pool, k))
        if abs((tot - s) / (len(pool) - k) - s / k) >= obs - 1e-12:
            hit += 1
    return (hit + 1) / (n + 1)


def bh(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    q, run = [0.0] * len(ps), 1.0
    for rank in range(len(ps), 0, -1):
        i = order[rank - 1]
        run = min(run, ps[i] * len(ps) / rank)
        q[i] = run
    return q


def v61_rules(W, H):
    src = open(os.path.join(ROOT, 'v61/main.cpp')).read()
    c = lambda name: int(re.search(rf'constexpr int {name} = (\d+);', src).group(1))
    cells, wide = W * H, W >= 2 * H
    return dict(
        center_map=cells <= c('CENTER_MAX_CELLS') and (wide or cells <= c('CENTER_SMALL_CELLS')),
        center_rounds=c('CENTER_ROUNDS') if wide else c('CENTER_SMALL_ROUNDS'),
        center_margin='none' if wide else c('CENTER_OUTNUMBER_MARGIN'),
        aggressive=cells <= c('AGGRESSIVE_MAX_CELLS'),
        queen_cells=cells > c('QUEEN_MIN_CELLS'),
        sonar=W <= c('SONAR_COORD_MAX') + 1 and H <= c('SONAR_COORD_MAX') + 1)


def fmt(v):
    return '-' if v is None else f'{v:.2f}' if abs(v) < 10 else f'{v:.1f}' if abs(v) < 100 else f'{v:.0f}'


def load(path):
    rows = [json.loads(l) for l in open(path)]
    with cf.ProcessPoolExecutor(min(6, int(os.environ.get('WORKERS', '6')))) as pool:
        return rows, list(pool.map(analyse, rows, chunksize=2))


def main(main_path, side_path=None, extra_path=None, out_path=None):
    rows, games = load(main_path)
    by = defaultdict(list)
    for g in games:
        by[(g['base'], g['tx'])].append(g)
    bases = sorted({g['base'] for g in games})
    txs = [t for t in MAIN_TX if any((b, t) in by for b in bases)]

    tests = []
    for b in bases:
        o = by[(b, 'identity')]
        for t in txs:
            for key, _ in METRICS:
                a = [g['m'][key] for g in o if g['m'][key] is not None]
                c = [g['m'][key] for g in by[(b, t)] if g['m'][key] is not None]
                if len(a) < 3 or len(c) < 3:
                    continue
                sd = ((statistics.pstdev(a) ** 2 + statistics.pstdev(c) ** 2) / 2) ** 0.5
                diff = statistics.mean(c) - statistics.mean(a)
                d = diff / sd if sd else math.copysign(math.inf, diff) if diff else 0.0
                tests.append(dict(base=b, tx=t, key=key, diff=diff, d=d, p=perm_p(a, c), a=a, c=c))
    for test, q in zip(tests, bh([x['p'] for x in tests])):
        test['q'] = q
    flag = {(x['base'], x['tx'], x['key']): x for x in tests}

    out = []
    w = out.append
    w('## Validation from replays\n')
    sets = [('main', rows, games)]
    if side_path:
        sets.append(('side swap', *load(side_path)))
    if extra_path:
        sets.append(('rot180/rot270/mirror_y', *load(extra_path)))
    for name, rs, gs in sets:
        bad = [r for r in rs if r['winner'] is None or r['rc'] or r['defects']]
        here, there = Counter(), Counter()
        for g in gs:
            if g['tx'] != 'identity':
                here.update(g['here'])
                there.update(g['there'])
        orig = Counter()
        for g in gs:
            if g['tx'] == 'identity':
                orig.update(g['here'])
        w(f'- {name}: {len(rs)} games, {len(bad)} without a result or with engine defect notices; '
          f"{sum(r['rounds'] == 500 for r in rs)} went 500 rounds, the rest ended by elimination")
        if orig:
            w(f'  - head moves on original maps: {dict(orig)}')
        w(f'  - head moves on transformed maps, own coordinates: {dict(here)}')
        w(f'  - the same moves mapped back onto the original map: {dict(there)}')
        if name == 'side swap':
            ref = {(g['map'], g['seed']): g['digest'] for g in games if g['side'] == 0}
            same = sum(ref.get((g['map'], g['seed'])) == g['digest'] for g in gs)
            w(f'  - event-identical to the side-0 game with the same map and seed: {same}/{len(gs)}')
    w('')
    w('## v61 size rules per variant\n')
    w('From the v61 constructor (main.cpp:403-412). outnumber margin: centre pull only while '
      'enemy heads - ally heads <= margin.\n')
    w('| map | variant | W x H | centre pull | centre rounds | outnumber margin | aggressive | queen cells | sonar |')
    w('|---|---|---|---|---|---|---|---|---|')
    for b in bases:
        for t in ('identity',) + tuple(txs):
            if (b, t) not in by:
                continue
            m = maptx.parse(open(maptx_path(b, t)).read())
            r = v61_rules(m['W'], m['H'])
            on = r['center_map']
            w(f"| {b} | {t} | {m['W']}x{m['H']} | {on} | {r['center_rounds'] if on else '-'} | "
              f"{r['center_margin'] if on else '-'} | {r['aggressive']} | {r['queen_cells']} | {r['sonar']} |")
    w('')
    w('## Per-map tables\n')
    w('Mean ± sd over seeds. `**` = flagged (Benjamini-Hochberg q < 0.05 over all tests), `*` = p < 0.01 only.\n')
    for b in bases:
        o = by[(b, 'identity')]
        m = original(b)[0]
        w(f"### {b} ({m['W']}x{m['H']}, SYMMETRY {m['sym']}, {len(o)} seeds)\n")
        cols = ['identity'] + txs
        w('| metric | ' + ' | '.join('original' if t == 'identity' else t for t in cols) + ' |')
        w('|---|' + '---|' * len(cols))
        ends = []
        for t in cols:
            c = Counter(g['how'] for g in by[(b, t)])
            win = Counter(g['winner'] for g in by[(b, t)])
            ends.append(' '.join(f'{k} {v}' for k, v in sorted(c.items())) + f" (A {win['A']}, B {win['B']})")
        w('| ends (winner) | ' + ' | '.join(ends) + ' |')
        for key, label in METRICS:
            cells = []
            for t in cols:
                v = [g['m'][key] for g in by[(b, t)] if g['m'][key] is not None]
                s = f'{fmt(statistics.mean(v))} ± {fmt(statistics.pstdev(v))}' if v else '-'
                x = flag.get((b, t, key))
                if x and x['q'] < 0.05:
                    s = f"**{s}** (d {x['d']:+.1f})"
                elif x and x['p'] < 0.01:
                    s = f"{s} * (d {x['d']:+.1f})"
                cells.append(s)
            w(f'| {label} | ' + ' | '.join(cells) + ' |')
        w('')
    w('## Compass check (steps before round 60, pooled over seeds)\n')
    w('Own frame = directions as the bot saw them; original frame = the same steps mapped back to the original map.\n')
    w('| map | variant | own E/(E+W) | own N/(N+S) | orig-frame E/(E+W) | orig-frame N/(N+S) | steps |')
    w('|---|---|---|---|---|---|---|')
    for b in bases:
        for t in ['identity'] + txs:
            own = Counter()
            for g in by[(b, t)]:
                own.update(g['own'])
            e = statistics.mean(g['m']['east60'] for g in by[(b, t)])
            n = statistics.mean(g['m']['north60'] for g in by[(b, t)])
            w(f"| {b} | {t} | {own['E'] / max(1, own['E'] + own['W']):.3f} | {own['N'] / max(1, own['N'] + own['S']):.3f} | "
              f"{e:.3f} | {n:.3f} | {sum(own.values())} |")
    w('')
    w('## Flag counts per variant (q < 0.05)\n')
    w('outcome = the requested metrics (ends, length, lengths, units, queen deaths, self deaths); '
      'mechanism = centre distance, compass shares, portal jumps.\n')
    w('| map | ' + ' | '.join(txs) + ' |')
    w('|---|' + '---|' * len(txs))
    for b in bases:
        cells = []
        for t in txs:
            hit = [x['key'] for x in tests if x['base'] == b and x['tx'] == t and x['q'] < 0.05]
            mech = sum(k in MECH for k in hit)
            cells.append(f'{len(hit) - mech} outcome, {mech} mechanism')
        w(f'| {b} | ' + ' | '.join(cells) + ' |')
    w('')
    w('## Flagged differences\n')
    hits = sorted((x for x in tests if x['q'] < 0.05), key=lambda x: x['p'])
    w(f'{len(tests)} tests; {len(hits)} with q < 0.05; {sum(x["p"] < 0.01 for x in tests)} with p < 0.01 '
      f'(about {0.01 * len(tests):.1f} expected by chance).\n')
    w('| map | variant | metric | original | transformed | diff | d | p | q |')
    w('|---|---|---|---|---|---|---|---|---|')
    label = dict(METRICS)
    for x in sorted((x for x in tests if x['p'] < 0.01), key=lambda x: (x['q'] >= 0.05, x['p'])):
        w(f"| {x['base']} | {x['tx']} | {label[x['key']]} | {fmt(statistics.mean(x['a']))} ± {fmt(statistics.pstdev(x['a']))} | "
          f"{fmt(statistics.mean(x['c']))} ± {fmt(statistics.pstdev(x['c']))} | {x['diff']:+.2f} | {x['d']:+.1f} | "
          f"{x['p']:.4f} | {x['q']:.3f}{' **' if x['q'] < 0.05 else ''} |")
    text = '\n'.join(out) + '\n'
    if out_path:
        open(out_path, 'w').write(text)
        json.dump([dict(g, m=g['m']) for g in games], open(os.path.splitext(out_path)[0] + '.json', 'w'))
    print(text)


def maptx_path(base, t):
    if t == 'identity':
        return os.path.join(ROOT, 'tune_runs/official127', base + '.map')
    return os.path.join(ROOT, 'tune_runs/tx_old10', f'{base}_{t}.map')


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        sys.exit(2)
    opt = lambda flag: a[a.index(flag) + 1] if flag in a else None
    main(a[0], opt('--side'), opt('--extra'), opt('--out'))
