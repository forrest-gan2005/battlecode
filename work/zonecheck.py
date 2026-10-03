#!/usr/bin/env python3
"""Queen safe-zone / corner mechanism check from kept replays with logs (work/zonerun.py).

usage: python3 zonecheck.py DIR BASE_TAG CAND_TAG [--maps a,b] [--list N]
Per game, our queen: death round/reason, alive at end; from the candidate's ZONE/CORNER logs: zone found,
approach, sonar checks, entry, rounds inside, rounds with the head next to the portal, exit reason.
"""
import argparse, glob, json, os, sys, concurrent.futures as cf
from collections import Counter, defaultdict, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

REASONS = ['wall', 'self', 'body', 'head', 'none']


def load_map(text):
    lines = text.splitlines()
    W, H = map(int, lines[0].split()[1:3])
    E = {}
    for l in lines:
        q = l.split()
        if q and q[0] == 'EDGE':
            E[int(q[1])] = int(q[2])
    return W, H, E


def edge(W, H, E, x, y, d):
    S = 2 * (W + 1)
    if d == 'N':
        return E.get(y * S + x, 0)
    if d == 'S':
        return E.get((y + 1) * S + x, 0) if y + 1 < H else E.get(H * S + x, E.get(x, 0))
    if d == 'W':
        return E.get(y * S + (W + 1) + x, 0)
    return E.get(y * S + (W + 1) + x + 1, 0)


def region(W, H, E, start, cap=400):
    seen = {start}
    q = [start]
    for c in q:
        for d, (dx, dy) in (('N', (0, -1)), ('E', (1, 0)), ('S', (0, 1)), ('W', (-1, 0))):
            if edge(W, H, E, c[0], c[1], d) != 0:
                continue
            n = ((c[0] + dx) % W, (c[1] + dy) % H)
            if n not in seen:
                seen.add(n)
                q.append(n)
                if len(q) > cap:
                    return seen
    return seen


def portal_cells(W, H, E, cells):
    return {c for c in cells if any(edge(W, H, E, c[0], c[1], d) == 2 for d in 'NESW')}


def scan(path, qid):
    """One pass: map text, winner, team of each dragon, our queen's head per round, length, death, logs."""
    msg = replay.load(path)
    root = msg.root()
    result = root.pointer(4)
    winner = ('A', 'B')[result.u16(6)] if result.u16(4) == 1 else None
    text = root.text(0)
    team_of = {}
    body = None
    for line in text.splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(team_of)
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
            if did == qid:
                body = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
    rnd = 0
    qpos, qlen, logs = {}, {}, []
    death = None
    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        if kind == 'roundStart':
            rnd = ev.pointer(0).i32(0)
        elif kind == 'dragonUpdate':
            pl = ev.pointer(0)
            if pl.i32(0) == qid and body is not None:
                head = replay.point(pl.pointer(0))
                tail = replay.point(pl.pointer(1))
                if not body or body[0] != head:
                    body.appendleft(head)
                while len(body) > 1 and body[-1] != tail:
                    body.pop()
                qpos[rnd] = head
                qlen[rnd] = len(body)
        elif kind == 'dragonSplit':
            pl = ev.pointer(0)
            parent, child = pl.i32(0), pl.i32(4)
            team_of[child] = ('A', 'B')[pl.u16(8)]
            if parent == qid:
                body = deque(replay.point(x) for x in pl.pointer(0))
        elif kind == 'dragonDeath':
            pl = ev.pointer(0)
            if pl.i32(0) == qid and death is None:
                r = pl.u16(4)
                death = (rnd, REASONS[r] if r < 5 else str(r), len(body) if body else 0)
        elif kind == 'dragonLog':
            pl = ev.pointer(0)
            logs.append((rnd, pl.i32(0), pl.text(0)))
    return text, winner, team_of, qpos, qlen, death, logs


def metrics(path, side):
    ours = 'A' if side == '0' else 'B'
    qid = 0 if ours == 'A' else 1
    text, winner, team_of, qpos, qlen, death, logs = scan(path, qid)
    W, H, E = load_map(text)
    m = dict(win=int(winner == ours), qdeath=None, qreason='', qlen=0, alive=1, found=None, approach=None,
             checks=0, clear=0, enter=None, inside=0, mouthside=0, exitr='', exit_round=None, corner=None, cnear=0,
             cescape=0, qend=qlen[max(qlen)] if qlen else 0, cportal=0, cknown=0, last_near=None, last_escape=None)
    if death:
        m['qdeath'], m['qreason'], m['qlen'] = death
        m['alive'] = 0
    for r, did, txt in logs:
        if team_of.get(did) != ours:
            continue
        t = txt.split()
        if not t:
            continue
        tag = t[0]
        if tag == 'ZFOUND' and m['found'] is None:
            m['found'] = r
        elif did != qid:
            continue
        elif tag == 'ZMODE' and t[1] == '1' and m['approach'] is None:
            m['approach'] = r
        elif tag == 'ZCHECK':
            m['checks'] += 1
            m['clear'] += int(t[1]) == 1 and all(int(v) == 0 for v in t[2:6])
        elif tag == 'ZENTER' and m['enter'] is None:
            m['enter'] = r
        elif tag in ('ZLEAVE', 'ZBAD', 'ZEXIT') and m['enter'] is not None and not m['exitr']:
            m['exitr'] = {'ZLEAVE': 'late' if t[1] == '1' else 'grown', 'ZBAD': 'invaded', 'ZEXIT': 'exit'}[tag]
            m['exit_round'] = r
        elif tag == 'CANCHOR':
            if m['corner'] is None:
                m['corner'] = r
            m['cportal'] = max(m['cportal'], int(t[3]) >= 0)
            m['cknown'] = max(m['cknown'], int(t[4]))
        elif tag == 'CNEAR':
            m['cnear'] += 1
            m['last_near'] = r
        elif tag == 'CESCAPE':
            m['cescape'] += 1
            m['last_escape'] = r
    if m['enter'] is not None:
        start = m['enter'] + 1
        end = min(x for x in (m['exit_round'], m['qdeath'], 500) if x is not None)
        zone = region(W, H, E, qpos.get(start, qpos.get(m['enter'], (0, 0))))
        mouth = portal_cells(W, H, E, zone)
        for r in range(start, end + 1):
            p = qpos.get(r)
            if p in zone:
                m['inside'] += 1
                m['mouthside'] += p in mouth
    return m


def safe_metrics(job):
    p, side = job
    cache = os.path.join(os.path.dirname(p), '.cache', os.path.basename(p) + '.json')
    try:
        if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(p):
            return json.load(open(cache))
        m = metrics(p, side)
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        json.dump(m, open(cache, 'w'))
        return m
    except Exception as ex:
        print('skip', p, ex, file=sys.stderr)
        return None


def collect(d, tag, maps):
    jobs, keys = [], []
    for p in glob.glob(os.path.join(d, f'{tag}_*.replay')):
        stem = os.path.basename(p)[len(tag) + 1:-len('.replay')]
        mp, seed, side = stem.rsplit('_', 2)
        if maps and mp not in maps:
            continue
        jobs.append((p, side))
        keys.append((mp, seed, side))
    with cf.ProcessPoolExecutor(int(os.environ.get('WORKERS', '4'))) as pool:
        res = list(pool.map(safe_metrics, jobs))
    return {k: m for k, m in zip(keys, res) if m is not None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir')
    ap.add_argument('base')
    ap.add_argument('cand')
    ap.add_argument('--maps')
    ap.add_argument('--list', type=int, default=0)
    a = ap.parse_args()
    maps = set(a.maps.split(',')) if a.maps else None
    base, cand = collect(a.dir, a.base, maps), collect(a.dir, a.cand, maps)
    keys = sorted(set(base) & set(cand))
    print(f'{len(keys)} paired games on {len({k[0] for k in keys})} maps')
    per = defaultdict(list)
    for k in keys:
        per[k[0]].append(k)
    hdr = f"{'map':30s} n  win b/c  qalive b/c  qdeath<300 b/c  found appr enter inside mouth exits"
    print(hdr)
    tot = Counter()
    for mp, ks in sorted(per.items()):
        b = [base[k] for k in ks]
        c = [cand[k] for k in ks]
        early = lambda xs: sum(1 for x in xs if x['qdeath'] is not None and x['qdeath'] < 300)
        exits = Counter(x['exitr'] for x in c if x['enter'] is not None)
        row = dict(n=len(ks), bw=sum(x['win'] for x in b), cw=sum(x['win'] for x in c), ba=sum(x['alive'] for x in b),
                   ca=sum(x['alive'] for x in c), be=early(b), ce=early(c), found=sum(x['found'] is not None for x in c),
                   appr=sum(x['approach'] is not None for x in c), enter=sum(x['enter'] is not None for x in c),
                   inside=sum(x['inside'] for x in c), mouth=sum(x['mouthside'] for x in c))
        for k2, v in row.items():
            tot[k2] += v
        print(f"{mp[:30]:30s} {row['n']:2d}  {row['bw']:2d}/{row['cw']:<2d}    {row['ba']:2d}/{row['ca']:<2d}       {row['be']:2d}/{row['ce']:<2d}"
              f"        {row['found']:3d} {row['appr']:4d} {row['enter']:5d} {row['inside']:6d} {row['mouth']:5d} {dict(exits)}")
    print(f"{'ALL':30s} {tot['n']:2d}  {tot['bw']}/{tot['cw']}    {tot['ba']}/{tot['ca']}       {tot['be']}/{tot['ce']}"
          f"        {tot['found']} {tot['appr']} {tot['enter']} {tot['inside']} {tot['mouth']}")
    cd = [cand[k]['qdeath'] or 500 for k in keys]
    bd = [base[k]['qdeath'] or 500 for k in keys]
    cd.sort(); bd.sort()
    print('queen death round median base', bd[len(bd) // 2], 'cand', cd[len(cd) // 2])
    print('checks', sum(cand[k]['checks'] for k in keys), 'clear', sum(cand[k]['clear'] for k in keys))
    reasons = Counter((cand[k]['qreason'] or 'alive') for k in keys)
    breasons = Counter((base[k]['qreason'] or 'alive') for k in keys)
    print('queen fate base', dict(breasons), 'cand', dict(reasons))
    if any(cand[k]['corner'] is not None for k in keys):
        early = lambda xs: sum(1 for x in xs if x['qdeath'] is not None and x['qdeath'] < 150)
        c = [cand[k] for k in keys]
        b = [base[k] for k in keys]
        print('corner: anchored', sum(x['corner'] is not None for x in c), 'with portal', sum(x['cportal'] for x in c),
              'exit known', sum(x['cknown'] for x in c), 'near-rounds', sum(x['cnear'] for x in c), 'escapes', sum(x['cescape'] for x in c),
              'games with escape', sum(x['cescape'] > 0 for x in c))
        print('queen deaths before r150 base', early(b), 'cand', early(c))
        dn = sum(1 for x in c if x['qdeath'] is not None and x['last_near'] is not None and x['qdeath'] - x['last_near'] <= 2)
        de = sum(1 for x in c if x['qdeath'] is not None and x['last_escape'] is not None and 0 <= x['qdeath'] - x['last_escape'] <= 15)
        print('cand queen deaths at the corner (near log within 2 rounds)', dn, 'within 15 rounds after an escape', de)
    if a.list:
        rows = [(k, cand[k]) for k in keys if cand[k]['enter'] is not None or cand[k]['cescape'] > 0]
        for k, m in rows[:a.list]:
            print(f"  {a.cand}_{k[0]}_{k[1]}_{k[2]}: found r{m['found']} approach r{m['approach']} enter r{m['enter']} inside {m['inside']} "
                  f"mouth {m['mouthside']} exit {m['exitr'] or '-'} r{m['exit_round']} qdeath r{m['qdeath']} {m['qreason']} | base qdeath r{base[k]['qdeath']} win {base[k]['win']}->{m['win']}")


if __name__ == '__main__':
    main()
