#!/usr/bin/env python3
"""Card #34 mechanism check (KEEP_GUARDS): do a few of our dragons stay near our queen through the feeding phase?

usage: python3 work/card_34_check.py --replays DIR --base base --candidate candidate --output FILE
Replays are DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1), paired by (map, seed, side).

Everything is rebuilt from the replay alone (no bot logs). At the start of every round from 420 on, while our queen
(dragon id 0/1) is alive, it counts our other dragons whose head is within 6 cells of her head ("guards near").
The gated number is the mean of min(guards near, 3) over those rounds: how many of the 3 guard slots are filled.

Pre-registered before any switch-on game was played (see PASS RULE). Queen survival, queen length, feeds, rams and
wins are reported as raw numbers and are NOT part of the pass rule: the local opponent is our own bot, which does
not hunt a lone queen, and 16 games per side cannot settle an outcome.
"""
import argparse, glob, hashlib, json, os, sys, concurrent.futures as cf
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# PASS RULE (fixed before seeing results)
SAME_UNTIL = 200     # every pair must be replay-identical through this round (feeding cannot start earlier)
TARGET_ROUNDS = 300  # base needs at least this many late rounds with our queen alive, over all games
TARGET_MAX = 2.0     # ... and must fill at most this many of the 3 slots on average (the hole is there)
FILLED_MIN = 2.0     # switch on: at least this many of the 3 slots filled on average
FILLED_GAIN = 0.5    # ... and at least this much above base

LATE = 420           # late window: feeding is on everywhere (it starts after round 300 or 400)
NEAR = 6             # "within about 6 cells" (the card); the bot itself uses her 7x7 view
SIGHT = 3
SLOTS = 3            # KG_COUNT
FEED_FROM = 200
AFTER = 20           # "the queen survived that approach" = still alive this many rounds later
CAUSE = ['wall', 'self', 'body', 'headon', 'none']


def gap(a, b, size):
    raw = abs(a - b)
    return min(raw, size - raw)


def one(job):
    path, side = job
    ours = 'A' if side == '0' else 'B'
    root = replay.load(path).root()
    text = root.text(0)
    W, H = map(int, text.splitlines()[0].split()[1:3])
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
    foe_queen = next((i for i in (0, 1) if team_of.get(i) not in (None, ours)), None)
    if queen is None:
        raise ValueError(f'no queen (dragon 0/1) for team {ours} in {path}')
    c = Counter(games=1, win=int(winner == ours), cells=W * H)
    prefix, sha = {}, hashlib.sha1()
    rnd, mover, last_round = 0, None, 0
    queen_died = None
    threat_on = False
    approaches, rams = [], []

    def manh(a, b):
        return gap(a[0], b[0], W) + gap(a[1], b[1], H)

    def near_queen():
        qh = bodies[queen][0]
        mine = [b[0] for d, b in bodies.items() if b and d != queen and team_of.get(d) == ours]
        n6 = sum(1 for h in mine if manh(h, qh) <= NEAR)
        n3 = sum(1 for h in mine if max(gap(h[0], qh[0], W), gap(h[1], qh[1], H)) <= SIGHT)
        return n6, n3

    def units():
        return sum(1 for d, b in bodies.items() if b and team_of.get(d) == ours)

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        pl = ev.pointer(0)
        if kind == 'roundStart':
            rnd = pl.i32(0)
            last_round = rnd
            prefix[rnd] = sha.hexdigest()
            sha.update(f'r{rnd}'.encode())
            alive = bool(bodies.get(queen))
            for mark in (300, 400):
                if rnd == mark:
                    c[f'reach{mark}'] += 1
                    c[f'queen_alive{mark}'] += alive
                    c[f'few_units{mark}'] += units() <= 5
                    c[f'units{mark}'] += units()
            if alive and rnd > FEED_FROM:
                qh = bodies[queen][0]
                threat = any(b and team_of.get(d) != ours and manh(b[0], qh) <= NEAR for d, b in bodies.items())
                c['threat_rounds'] += threat
                if threat and not threat_on:
                    approaches.append((rnd, near_queen()[0]))
                threat_on = threat
            if alive and rnd >= LATE:
                n6, n3 = near_queen()
                c['late_rounds'] += 1
                c['late_filled'] += min(n6, SLOTS)
                c['late_filled_sight'] += min(n3, SLOTS)
                c['late_alone'] += n6 == 0
                c['late_full'] += n6 >= SLOTS
                c['late_units'] += units()
        elif kind == 'dragonAction':
            mover = pl.i32(0)
            usage = pl.pointer(1)
            if usage and team_of.get(mover) == ours:
                c['cpu_max'] = max(c['cpu_max'], usage.u64(0))
            a = pl.pointer(0)
            if a is not None and a.u16(0) == 2 and team_of.get(mover) == ours:
                c['suicides'] += 1
                c['feeds'] += rnd > FEED_FROM
                c['feeds_late'] += rnd >= LATE
                c['queen_suicides'] += mover == queen
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            h = replay.point(pl.pointer(0))
            tp = replay.point(pl.pointer(1))
            sha.update(f'u{did}{h}{tp}'.encode())
            b = bodies.setdefault(did, deque())
            if not b or b[0] != h:
                b.appendleft(h)
            while len(b) > 1 and b[-1] != tp:
                b.pop()
        elif kind == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            sha.update(f's{pa}{ch}'.encode())
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0))
            bodies[ch] = deque(replay.point(x) for x in pl.pointer(1))
            team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
        elif kind == 'dragonDeath':
            did = pl.i32(0)
            r = pl.u16(4)
            sha.update(f'd{did}{r}'.encode())
            cause = CAUSE[r] if r < 5 else 'other'
            b = bodies.get(did)
            if team_of.get(did) == ours and b:
                if did == queen:
                    queen_died = rnd
                    c[f'queen_death_{cause}'] += 1
                    c['queen_death_own_turn'] += mover == queen
                elif cause == 'headon' and rnd > FEED_FROM and bodies.get(queen) and manh(b[0], bodies[queen][0]) <= NEAR + 2:
                    rams.append((rnd, mover == did))
                if did != queen and rnd > FEED_FROM:
                    c[f'late_death_{cause}'] += 1
            bodies.pop(did, None)
    prefix[last_round + 1] = sha.hexdigest()

    def held(r):
        return queen_died is None or queen_died > r + AFTER

    alive = bool(bodies.get(queen))
    c['queen_alive_end'] = int(alive)
    c['last_round'] = last_round
    c['units_end'] = units()
    mine = [len(b) for d, b in bodies.items() if b and team_of.get(d) == ours]
    c['total_end'] = sum(mine)
    c['queen_len_end'] = len(bodies[queen]) if alive else 0
    c['kept_back_end'] = sum(mine) - c['queen_len_end']
    foe_alive = bool(foe_queen is not None and bodies.get(foe_queen))
    c['foe_queen_alive_end'] = int(foe_alive)
    c['foe_queen_len_end'] = len(bodies[foe_queen]) if foe_alive else 0
    if alive:
        n6, n3 = near_queen()
        c['end_near'] = n6
        c['end_has_guard'] = int(n6 >= 1)
        c['end_full'] = int(n6 >= SLOTS)
    c['approaches'] = len(approaches)
    c['approaches_survived'] = sum(held(r) for r, _ in approaches)
    c['approaches_guarded'] = sum(n > 0 for _, n in approaches)
    c['approaches_guarded_survived'] = sum(held(r) for r, n in approaches if n > 0)
    c['guard_rams'] = sum(1 for _, own in rams if own)
    c['guard_rams_survived'] = sum(held(r) for r, own in rams if own)
    c['guards_rammed'] = sum(1 for _, own in rams if not own)
    out = dict(c)
    out['prefix'] = prefix
    out['queen_died'] = queen_died
    return out


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
        s.update({k: v for k, v in r.items() if isinstance(v, int)})
        s['cpu_max'] = cpu
    return s


def share(a, b):
    return a / b if b else 0.0


def first_diff(b, c):
    """First round whose events differ between the two games of a pair; None when the games are identical."""
    last = max(max(b['prefix']), max(c['prefix']))
    for r in range(2, last + 1):
        if b['prefix'].get(r) != c['prefix'].get(r):
            return r - 1
    return None


def view(s):
    games = s['games']
    both = s['both_queens_end']
    return {
        'games': games, 'wins': s['win'], 'cpu_max_points': s['cpu_max'],
        'late_rounds_queen_alive': s['late_rounds'],
        'slots_filled_mean': round(share(s['late_filled'], s['late_rounds']), 3),
        'slots_filled_mean_in_her_view': round(share(s['late_filled_sight'], s['late_rounds']), 3),
        'late_rounds_alone': s['late_alone'], 'late_rounds_all_slots': s['late_full'],
        'alone_share': round(share(s['late_alone'], s['late_rounds']), 3),
        'our_dragons_late_mean': round(share(s['late_units'], s['late_rounds']), 1),
        'games_reaching_r300': s['reach300'], 'games_reaching_r400': s['reach400'],
        'games_5_or_fewer_dragons_at_r300': s['few_units300'], 'games_5_or_fewer_dragons_at_r400': s['few_units400'],
        'queen_alive_at_r400': s['queen_alive400'], 'queen_alive_at_end': s['queen_alive_end'],
        'queen_deaths_by_cause': {k: s[f'queen_death_{k}'] for k in CAUSE if s[f'queen_death_{k}']},
        'queen_deaths_on_her_own_turn': s['queen_death_own_turn'],
        'queen_fed_herself': s['queen_suicides'],
        'end_games_with_a_guard_near': s['end_has_guard'], 'end_games_with_all_slots': s['end_full'],
        'our_dragons_at_end_mean': round(share(s['units_end'], games), 1),
        'queen_len_end_mean_when_alive': round(share(s['queen_len_end'], s['queen_alive_end']), 1),
        'kept_back_len_end_mean': round(share(s['kept_back_end'], games), 1),
        'total_len_end_mean': round(share(s['total_end'], games), 1),
        'both_queens_alive_at_end': both, 'of_those_our_queen_longer': s['both_ours_longer'],
        'feeds_after_r200': s['feeds'], 'feeds_from_r420': s['feeds_late'],
        'enemy_approaches': s['approaches'], 'approaches_queen_alive_20_rounds_later': s['approaches_survived'],
        'approaches_with_a_guard_near': s['approaches_guarded'],
        'guarded_approaches_queen_alive_20_rounds_later': s['approaches_guarded_survived'],
        'guard_rams': s['guard_rams'], 'guard_rams_queen_alive_20_rounds_later': s['guard_rams_survived'],
        'guards_rammed_by_enemy': s['guards_rammed'],
        'rounds_enemy_head_near_queen': s['threat_rounds'],
    }


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
    for rows in (base, cand):
        for r in rows.values():
            both = r['queen_alive_end'] and r['foe_queen_alive_end']
            r['both_queens_end'] = int(both)
            r['both_ours_longer'] = int(both and r['queen_len_end'] > r['foe_queen_len_end'])
    diffs = {k: first_diff(base[k], cand[k]) for k in keys}
    changed = sorted(d for d in diffs.values() if d is not None)
    early = sorted('_'.join(k) for k, d in diffs.items() if d is not None and d <= SAME_UNTIL)
    b, c = total(base[k] for k in keys), total(cand[k] for k in keys)
    bv, cv = view(b), view(c)
    saved = sum(1 for k in keys if cand[k]['queen_alive_end'] and not base[k]['queen_alive_end'])
    lost = sum(1 for k in keys if base[k]['queen_alive_end'] and not cand[k]['queen_alive_end'])
    by_map = {}
    for m in sorted({k[0] for k in keys}):
        mb, mc = total(base[k] for k in keys if k[0] == m), total(cand[k] for k in keys if k[0] == m)
        by_map[m] = {'cells': mb['cells'] // max(1, mb['games']), 'games': mb['games'],
                     'slots_filled_mean': [round(share(mb['late_filled'], mb['late_rounds']), 2),
                                           round(share(mc['late_filled'], mc['late_rounds']), 2)],
                     'late_rounds_queen_alive': [mb['late_rounds'], mc['late_rounds']],
                     'feeds_after_r200': [mb['feeds'], mc['feeds']],
                     'queen_alive_at_end': [mb['queen_alive_end'], mc['queen_alive_end']],
                     'queen_len_end_mean_when_alive': [round(share(mb['queen_len_end'], mb['queen_alive_end']), 1),
                                                       round(share(mc['queen_len_end'], mc['queen_alive_end']), 1)],
                     'wins': [mb['win'], mc['win']]}

    prefix_ok = not early
    target_seen = bv['late_rounds_queen_alive'] >= TARGET_ROUNDS and bv['slots_filled_mean'] <= TARGET_MAX
    guards_ok = (cv['late_rounds_queen_alive'] > 0 and cv['slots_filled_mean'] >= FILLED_MIN and
                 cv['slots_filled_mean'] >= bv['slots_filled_mean'] + FILLED_GAIN)
    passed = bool(prefix_ok and target_seen and guards_ok)
    why = []
    if not prefix_ok:
        why.append(f'{len(early)} pairs differ at or before round {SAME_UNTIL}, before feeding can start')
    if not target_seen:
        why.append(f"base did not show the hole (needs {TARGET_ROUNDS}+ late rounds with the queen alive and at most "
                   f"{TARGET_MAX} slots filled; got {bv['late_rounds_queen_alive']} rounds, {bv['slots_filled_mean']} filled)")
    if not guards_ok:
        why.append(f'guard slots filled did not reach {FILLED_MIN} of 3 and base + {FILLED_GAIN}')
    note = (f"guard slots filled (our dragons within {NEAR} cells of our queen, max 3, mean over rounds {LATE}+ with her alive): "
            f"base {bv['slots_filled_mean']} -> switch on {cv['slots_filled_mean']} "
            f"({bv['late_rounds_queen_alive']} and {cv['late_rounds_queen_alive']} rounds); "
            f"rounds with nobody near her {bv['alone_share']:.0%} -> {cv['alone_share']:.0%}; "
            f"pairs that differ: {len(changed)}/{len(keys)}, earliest at round {changed[0] if changed else 'never'}; "
            f"not gated, {len(keys)} games each: feeds after r200 {bv['feeds_after_r200']} -> {cv['feeds_after_r200']}, "
            f"queen alive at end {bv['queen_alive_at_end']} -> {cv['queen_alive_at_end']} (saved {saved}, lost {lost}), "
            f"queen length at end when alive {bv['queen_len_end_mean_when_alive']} -> {cv['queen_len_end_mean_when_alive']}, "
            f"guard rams {bv['guard_rams']} -> {cv['guard_rams']}, "
            f"games with 5 or fewer dragons at r400 {bv['games_5_or_fewer_dragons_at_r400']} -> "
            f"{cv['games_5_or_fewer_dragons_at_r400']}, queen fed herself {bv['queen_fed_herself']} -> {cv['queen_fed_herself']}, "
            f"wins {bv['wins']} -> {cv['wins']}"
            + ('' if passed else '. NOT shown: ' + '; '.join(why)))
    out = {'passed': passed, 'note': note, 'target_seen': bool(target_seen), 'pairs': len(keys),
           'maps': sorted({k[0] for k in keys}),
           'pass_rule': {'same_until_round': SAME_UNTIL, 'target_rounds': TARGET_ROUNDS, 'target_max': TARGET_MAX,
                         'filled_min': FILLED_MIN, 'filled_gain': FILLED_GAIN, 'prefix_ok': bool(prefix_ok),
                         'target_seen': bool(target_seen), 'guards_ok': bool(guards_ok)},
           'base': bv, 'candidate': cv, 'by_map_base_then_candidate': by_map,
           'pairs_that_differ': len(changed), 'first_differing_rounds': changed, 'pairs_differing_too_early': early,
           'queen_alive_at_end_pairs': {'saved_by_switch': saved, 'lost_with_switch': lost},
           'limits': ('measured from replays without bot logs: "guard" here is any of our dragons within 6 cells of the queen, '
                      'whether or not the bot counted it as one; a guard ram is one of our dragons dying head-on on its own '
                      'move within 8 cells of the queen after round 200; an enemy approach is an enemy head coming within 6 '
                      'cells of her; base games count the same events, so base "guard rams" are its ordinary rams that happened '
                      'near her; cpu_max_points is 0 when the replays carry no CPU counter; survival, length, feeds, rams and '
                      'wins are raw counts from a small sample against our own bot, not evidence of an outcome')}
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
        sys.exit(f'card 34 check failed: {exc}')
