#!/usr/bin/env python3
"""Card #29 mechanism check (STRIDE_SAFE_END): do long dragons and the queen stop ending strides next to unseen tiles?

usage: python3 work/card_29_check.py --replays DIR --base base --candidate candidate --output FILE
Replays are DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1), paired by (map, seed, side).

For every move of our dragons of length 5+ it rebuilds, from the replay alone, what the bot could see when it
decided (the 7x7 box around the head before the move) and counts the tiles within 2 walking steps of the tile
where the head stopped that were outside that box ("unseen near the end"). A multi-step move is "risky" when
that count is above what the switch tolerates for the mover: 4 - length/4 (never below 0), and 0 for the queen.
Other multi-step moves (escapes, hunts, rams) are not changed by the switch and need an enemy nearby, so the
gate looks at "calm" moves only: no enemy head within 6 tiles of the mover.

Pre-registered before any game was played (see PASS RULE below). Deaths, pearls, length and CPU are reported as
raw numbers and are NOT part of the pass rule: 16 games per side cannot settle them, the A/B does.
"""
import argparse, glob, json, os, sys, concurrent.futures as cf
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# PASS RULE (fixed before seeing results)
TARGET_MIN = 30      # base must show at least this many calm risky ends by long dragons + queen (target seen)
CUT = 0.25           # candidate's calm risky share must be at most this fraction of base's
SHORT_KEEP = 0.8     # length 5-7 dragons keep at least this fraction of base's multi-step rate

VIEW = 3             # the bot sees a 7x7 box around its head
RADIUS = 2           # STRIDE_SAFE_RADIUS
UNSEEN = 4           # STRIDE_SAFE_UNSEEN
LONG = 8             # LONG_SAFE_MIN_LENGTH
CALM_GAP = 6
CAUSE = ['wall', 'self', 'body', 'headon', 'none']
TIERS = ('short', 'long', 'queen')
STEPS = (('N', 0, -1), ('E', 1, 0), ('S', 0, 1), ('W', -1, 0))


def load_map(text):
    lines = text.splitlines()
    W, H = map(int, lines[0].split()[1:3])
    E = {}
    for l in lines:
        q = l.split()
        if q and q[0] == 'EDGE':
            E[int(q[1])] = int(q[2])
    padded = len(E) == (2 * H + 1) * (W + 1)
    S = 2 * (W + 1)

    def blocked(x, y, d):
        """Kelp or portal on that side of the tile (portals are not walked here)."""
        if not padded:
            return False
        if d == 'N':
            ids = [y * S + x] + ([H * S + x] if y == 0 else [])
        elif d == 'S':
            ids = [(y + 1) * S + x] + ([x] if y == H - 1 else [])
        elif d == 'W':
            ids = [y * S + (W + 1) + x] + ([y * S + (W + 1) + W] if x == 0 else [])
        else:
            ids = [y * S + (W + 1) + x + 1] + ([y * S + (W + 1)] if x == W - 1 else [])
        return any(E.get(i, 0) != 0 for i in ids)

    return W, H, blocked, padded


def gap(a, b, size):
    raw = abs(a - b)
    return min(raw, size - raw)


def unseen_near(W, H, blocked, others, start, end):
    """Tiles within RADIUS walking steps of `end` that lie outside the 7x7 box around `start`."""
    def in_view(c):
        return gap(c[0], start[0], W) <= VIEW and gap(c[1], start[1], H) <= VIEW
    seen, frontier, unseen = {end}, [end], 0
    for _ in range(RADIUS):
        nxt = []
        for x, y in frontier:
            for d, dx, dy in STEPS:
                if blocked(x, y, d):
                    continue
                n = ((x + dx) % W, (y + dy) % H)
                if n in seen or (n in others and in_view(n)):
                    continue
                seen.add(n)
                nxt.append(n)
                unseen += not in_view(n)
        frontier = nxt
    return unseen


def tolerated(tier, length):
    return 0 if tier == 'queen' else max(0, UNSEEN - length // 4)


def one(job):
    path, side = job
    ours = 'A' if side == '0' else 'B'
    root = replay.load(path).root()
    text = root.text(0)
    W, H, blocked, padded = load_map(text)
    result = root.pointer(4)
    winner = ('A', 'B')[result.u16(6)] if result.u16(4) == 1 else None
    bodies, team_of = {}, {}
    for line in text.splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
    queen = next((i for i in (0, 1) if team_of.get(i) == ours), None)
    c = Counter(games=1, win=int(winner == ours), walls=int(padded))
    pending = None
    rnd = 0

    def close():
        nonlocal pending
        p, pending = pending, None
        if p is None:
            return
        t = p['tier']
        c[f'{t}_moves'] += 1
        c[f'{t}_steps'] += p['n']
        c[f'{t}_calm_moves'] += p['calm']
        if p['n'] < 2:
            return
        c['path_checked'] += not p['dead']
        c['path_mismatch'] += p['seen'] != p['n'] and not p['dead']
        risky = unseen_near(W, H, blocked, p['others'], p['start'], p['end']) > tolerated(t, p['len'])
        c[f'{t}_multi'] += 1
        c[f'{t}_risky'] += risky
        c[f'{t}_calm_multi'] += p['calm']
        c[f'{t}_calm_risky'] += risky and p['calm']

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        pl = ev.pointer(0)
        if kind == 'roundStart':
            close()
            rnd = pl.i32(0)
            if rnd == 300:
                c['total300'] = sum(len(b) for d, b in bodies.items() if b and team_of.get(d) == ours)
                c['units300'] = sum(1 for d, b in bodies.items() if b and team_of.get(d) == ours)
        elif kind == 'dragonAction':
            close()
            mover = pl.i32(0)
            if team_of.get(mover) != ours:
                continue
            usage = pl.pointer(1)
            if usage:
                c['cpu_max'] = max(c['cpu_max'], usage.u64(0))
            a = pl.pointer(0)
            body = bodies.get(mover)
            if a is None or a.u16(0) != 0 or not body or len(body) < 5:
                continue
            try:
                n = max(1, len(a.pointer(0)))
            except Exception:
                n = 1
            head = body[0]
            foes = [b[0] for d, b in bodies.items() if b and team_of.get(d) != ours]
            calm = all(max(gap(f[0], head[0], W), gap(f[1], head[1], H)) > CALM_GAP for f in foes)
            others = {cell for d, b in bodies.items() if d != mover for cell in b} if n >= 2 else ()
            pending = dict(id=mover, len=len(body), start=head, end=head, n=n, seen=0, dead=False, calm=calm, others=others,
                           tier='queen' if mover == queen else 'long' if len(body) >= LONG else 'short')
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            h = replay.point(pl.pointer(0))
            tp = replay.point(pl.pointer(1))
            b = bodies.setdefault(did, deque())
            before = len(b)
            if not b or b[0] != h:
                b.appendleft(h)
                if pending and pending['id'] == did:
                    pending['seen'] += 1
                    pending['end'] = h
            while len(b) > 1 and b[-1] != tp:
                b.pop()
            if team_of.get(did) == ours and before > 0 and len(b) > before:
                c['eats'] += 1
        elif kind == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0))
            bodies[ch] = deque(replay.point(x) for x in pl.pointer(1))
            team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
        elif kind == 'dragonDeath':
            did = pl.i32(0)
            r = pl.u16(4)
            if pending and pending['id'] == did:
                pending['dead'] = True
            b = bodies.pop(did, None)
            if team_of.get(did) != ours or not b:
                continue
            cause = CAUSE[r] if r < 5 else 'other'
            if did == queen:
                c['queen_deaths'] += 1
                c[f'queen_deaths_{cause}'] += 1
            elif len(b) >= 5:
                c['deaths5'] += 1
                c[f'deaths5_{cause}'] += 1
                c['deaths8'] += len(b) >= LONG
                c['deaths5_before300'] += rnd < 300
    close()
    return dict(c)


def collect(directory, tag):
    jobs, keys = [], []
    for p in sorted(glob.glob(os.path.join(directory, f'{tag}_*.replay'))):
        stem = os.path.basename(p)[len(tag) + 1:-len('.replay')]
        m, seed, side = stem.rsplit('_', 2)
        jobs.append((p, side))
        keys.append((m, seed, side))
    with cf.ProcessPoolExecutor(int(os.environ.get('CHECK_WORKERS', '4'))) as pool:
        return dict(zip(keys, pool.map(one, jobs)))


def total(rows):
    s = Counter()
    for r in rows:
        cpu = max(s['cpu_max'], r.get('cpu_max', 0))
        s.update(r)
        s['cpu_max'] = cpu
    return s


def share(a, b):
    return a / b if b else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--replays', required=True)
    ap.add_argument('--base', required=True)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    base, cand = collect(a.replays, a.base), collect(a.replays, a.candidate)
    if not base or set(base) != set(cand):
        sys.exit(f'missing or unpaired replays in {a.replays}: {len(base)} {a.base}, {len(cand)} {a.candidate}')
    keys = sorted(base)
    b, c = total(base[k] for k in keys), total(cand[k] for k in keys)
    checked = b['path_checked'] + c['path_checked']
    if checked and (b['path_mismatch'] + c['path_mismatch']) > 0.02 * checked:
        sys.exit('replay moves do not line up with head updates; the measurement is not valid')

    def calm(s, field):
        return s[f'long_calm_{field}'] + s[f'queen_calm_{field}']

    def view(s):
        out = {'games': s['games'], 'wins': s['win'], 'cpu_max_points': s['cpu_max'],
               'calm_multi_long_queen': calm(s, 'multi'), 'calm_risky_long_queen': calm(s, 'risky'),
               'calm_risky_share_long_queen': round(share(calm(s, 'risky'), calm(s, 'multi')), 4),
               'deaths_len5plus': s['deaths5'], 'deaths_len8plus': s['deaths8'], 'deaths_len5plus_before_r300': s['deaths5_before300'],
               'deaths_len5plus_by_cause': {k: s[f'deaths5_{k}'] for k in CAUSE if s[f'deaths5_{k}']},
               'queen_deaths': s['queen_deaths'],
               'queen_deaths_by_cause': {k: s[f'queen_deaths_{k}'] for k in CAUSE if s[f'queen_deaths_{k}']},
               'pearls_eaten_per_game': round(share(s['eats'], s['games']), 1),
               'total_length_r300_per_game': round(share(s['total300'], s['games']), 1),
               'dragons_r300_per_game': round(share(s['units300'], s['games']), 1)}
        for t in TIERS:
            out[t] = {'moves': s[f'{t}_moves'], 'multi_step': s[f'{t}_multi'], 'risky_ends': s[f'{t}_risky'],
                      'calm_multi_step': s[f'{t}_calm_multi'], 'calm_risky_ends': s[f'{t}_calm_risky'],
                      'multi_step_rate': round(share(s[f'{t}_multi'], s[f'{t}_moves']), 4),
                      'mean_steps': round(share(s[f'{t}_steps'], s[f'{t}_moves']), 3)}
        return out

    bv, cv = view(b), view(c)
    target_seen = bv['calm_risky_long_queen'] >= TARGET_MIN
    cut_ok = cv['calm_risky_share_long_queen'] <= CUT * bv['calm_risky_share_long_queen']
    short_ok = cv['short']['multi_step_rate'] >= SHORT_KEEP * bv['short']['multi_step_rate']
    passed = bool(target_seen and cut_ok and short_ok)
    why = []
    if not target_seen:
        why.append(f"base showed only {bv['calm_risky_long_queen']} calm risky stride ends (need {TARGET_MIN})")
    if not cut_ok:
        why.append('the risky share did not fall to a quarter of base')
    if not short_ok:
        why.append('length 5-7 dragons lost more than a fifth of their multi-step moves')
    note = (f"calm multi-step moves by length-8+ dragons and the queen that end next to more unseen tiles than tolerated: "
            f"base {bv['calm_risky_long_queen']}/{bv['calm_multi_long_queen']} ({bv['calm_risky_share_long_queen']:.1%}) -> "
            f"switch on {cv['calm_risky_long_queen']}/{cv['calm_multi_long_queen']} ({cv['calm_risky_share_long_queen']:.1%}); "
            f"multi-step rate short {bv['short']['multi_step_rate']:.1%} -> {cv['short']['multi_step_rate']:.1%}, "
            f"long {bv['long']['multi_step_rate']:.1%} -> {cv['long']['multi_step_rate']:.1%}, "
            f"queen {bv['queen']['multi_step_rate']:.1%} -> {cv['queen']['multi_step_rate']:.1%}; "
            f"not gated, {len(keys)} games each: deaths of length 5+ {bv['deaths_len5plus']} -> {cv['deaths_len5plus']}, "
            f"queen deaths {bv['queen_deaths']} -> {cv['queen_deaths']}, pearls/game {bv['pearls_eaten_per_game']} -> "
            f"{cv['pearls_eaten_per_game']}, total length at r300 {bv['total_length_r300_per_game']} -> "
            f"{cv['total_length_r300_per_game']}, "
            + (f"peak CPU {bv['cpu_max_points']} -> {cv['cpu_max_points']}" if bv['cpu_max_points'] or cv['cpu_max_points']
               else 'CPU not measured (these replays carry no CPU counter)')
            + ('' if passed else '. NOT shown: ' + '; '.join(why)))
    out = {'passed': passed, 'note': note, 'target_seen': bool(target_seen), 'pairs': len(keys),
           'maps': sorted({k[0] for k in keys}),
           'pass_rule': {'target_min': TARGET_MIN, 'cut': CUT, 'short_keep': SHORT_KEEP,
                         'target_seen': bool(target_seen), 'cut_ok': bool(cut_ok), 'short_ok': bool(short_ok)},
           'base': bv, 'candidate': cv,
           'path_check': {'multi_step_moves': checked, 'mismatched': b['path_mismatch'] + c['path_mismatch']},
           'walls_modelled_games': b['walls'] + c['walls'],
           'limits': ('measured from replays without bot logs: the 7x7 view and kelp walls are rebuilt, portals are not walked '
                      'and remembered-but-unseen tiles count as unseen; the queen full-reach rule and the way-out rule are not '
                      'measured here; calm = no enemy head within 6 tiles, so escapes/hunts/rams are left out; deaths, pearls, '
                      'length and CPU are raw counts from a small sample, not evidence of an outcome')}
    with open(a.output, 'w') as f:
        json.dump(out, f, indent=2)
        f.write('\n')
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        sys.exit(f'card 29 check failed: {exc}')
