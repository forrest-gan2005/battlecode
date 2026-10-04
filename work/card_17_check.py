#!/usr/bin/env python3
"""Card #17 mechanism check (LG_AVENGE): once our queen is dead, short non-leaders go for theirs.

usage: python3 work/card_17_check.py --replays DIR --base base --candidate candidate --output FILE
Reads paired replays DIR/<tag>_<map>_<seed>_<side>.replay (side 0 = we are team A).

Expectation, written before any result was seen:
  1. identity: each pair is replay-identical until the round our queen dies in the base game
     (all the way if she survives).
  2. approach: in pairs where the base game has our queen dead and theirs alive for at least
     MIN_WINDOW rounds from HUNT_ROUND on, our hunters (alive, length <= MAX_LEN, not our longest)
     are on average closer to her head with the switch on, in more than half of those pairs.
  3. kills: in those pairs her deaths in that phase are not fewer than in base.
passed = 1 and 2 and 3, and it needs at least MIN_PAIRS such pairs (otherwise "not shown").
Exit code 0 for a completed measurement, nonzero for missing or unpaired replays.
"""
import argparse, glob, hashlib, json, os, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

HUNT_ROUND = 300
MAX_LEN = 8
MIN_WINDOW = 20
MIN_PAIRS = 3
NEAR = 3
REASONS = ['wall', 'self', 'body', 'head-on', 'no action']


def scan(path, ours):
    """One pass: per-round digests, queen deaths, and the hunt-phase distances for our side."""
    root = replay.load(path).root()
    text = root.text(0)
    W, H = map(int, text.splitlines()[0].split()[1:3])
    bodies, team_of = {}, {}
    for line in text.splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
    queens = [i for i in (0, 1) if team_of.get(i) == ours]
    foes = [i for i in (0, 1) if i in team_of and team_of[i] != ours]
    if len(queens) != 1 or len(foes) != 1:
        raise ValueError(f'{path}: ids 0 and 1 are not one queen per team')
    q_us, q_them = queens[0], foes[0]

    digests, h = {}, hashlib.sha1()
    death = {}
    rows = []
    our_small_deaths = 0
    rnd = 0

    def dist(a, b):
        dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
        return min(dx, W - dx) + min(dy, H - dy)

    def snapshot():
        # State at the end of round rnd: our queen dead, theirs alive, hunt phase.
        if rnd < HUNT_ROUND or q_us in bodies or q_them not in bodies:
            return
        mine = {i: len(b) for i, b in bodies.items() if team_of.get(i) == ours}
        if not mine:
            return
        lead = min(mine, key=lambda i: (-mine[i], i))
        her = bodies[q_them][0]
        d = [dist(bodies[i][0], her) for i, n in mine.items() if i != lead and n <= MAX_LEN]
        rows.append((rnd, sum(d) / len(d) if d else None, min(d) if d else None))

    for ev in root.pointer(3):
        kind = replay.EVENT_NAMES[ev.u16(0)] if ev.u16(0) < len(replay.EVENT_NAMES) else '?'
        pl = ev.pointer(0)
        if kind == 'roundStart':
            if rnd:
                snapshot()
                digests[rnd] = h.hexdigest()
            rnd = pl.i32(0)
            h = hashlib.sha1()
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            head, tail = replay.point(pl.pointer(0)), replay.point(pl.pointer(1))
            h.update(f'u{did}{head}{tail}'.encode())
            body = bodies.setdefault(did, deque())
            if not body or body[0] != head:
                body.appendleft(head)
            while len(body) > 1 and body[-1] != tail:
                body.pop()
        elif kind == 'dragonSplit':
            parent, child = pl.i32(0), pl.i32(4)
            h.update(f's{parent}{child}'.encode())
            team = ('A', 'B')[pl.u16(8)]
            bodies[parent] = deque(replay.point(p) for p in pl.pointer(0))
            bodies[child] = deque(replay.point(p) for p in pl.pointer(1))
            team_of[parent] = team_of[child] = team
        elif kind == 'dragonDeath':
            did, reason = pl.i32(0), pl.u16(4)
            h.update(f'd{did}{reason}'.encode())
            if did in (q_us, q_them):
                death[did] = (rnd, REASONS[reason] if reason < len(REASONS) else '?')
            elif (team_of.get(did) == ours and rnd >= HUNT_ROUND and q_us not in bodies and q_them in bodies
                  and len(bodies.get(did, ())) <= MAX_LEN):
                our_small_deaths += 1
            bodies.pop(did, None)
    if rnd:
        snapshot()
        digests[rnd] = h.hexdigest()

    mine = [len(b) for i, b in bodies.items() if team_of.get(i) == ours]
    theirs = [len(b) for i, b in bodies.items() if team_of.get(i) != ours]
    hunted = [r for r in rows if r[1] is not None]
    d_us, d_them = death.get(q_us), death.get(q_them)
    return {
        'digests': digests,
        'rounds': rnd,
        'queen_death': d_us[0] if d_us else None,
        'foe_death': d_them[0] if d_them else None,
        'foe_death_reason': d_them[1] if d_them else None,
        # Her death counts for the hunt only if our queen was already dead and the hunt phase had begun.
        'foe_killed_in_hunt': bool(d_them and d_us and d_them[0] >= max(HUNT_ROUND, d_us[0])),
        'window_rounds': len(rows),
        'hunter_rounds': len(hunted),
        'mean_dist': sum(r[1] for r in hunted) / len(hunted) if hunted else None,
        'near_rounds': sum(1 for r in hunted if r[2] <= NEAR),
        'small_deaths_in_hunt': our_small_deaths,
        'end_only_their_queen': q_us not in bodies and q_them in bodies,
        'end_both_dead': q_us not in bodies and q_them not in bodies,
        'end_longest_us': max(mine, default=0),
        'end_longest_them': max(theirs, default=0),
        'end_units_us': len(mine),
    }


def first_diff(a, b):
    for r in sorted(set(a) | set(b)):
        if a.get(r) != b.get(r):
            return r
    return None


def collect(directory, tag):
    out = {}
    for p in sorted(glob.glob(os.path.join(directory, f'{tag}_*.replay'))):
        stem = os.path.basename(p)[len(tag) + 1:-len('.replay')]
        m, seed, side = stem.rsplit('_', 2)
        out[(m, seed, side)] = p
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--replays', required=True)
    ap.add_argument('--base', required=True)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    base, cand = collect(a.replays, a.base), collect(a.replays, a.candidate)
    if not base or set(base) != set(cand):
        sys.exit(f'missing or unpaired replays: base {len(base)}, candidate {len(cand)}, '
                 f'unpaired {sorted(set(base) ^ set(cand))[:5]}')

    pairs = []
    for key in sorted(base):
        ours = 'A' if key[2] == '0' else 'B'
        b, c = scan(base[key], ours), scan(cand[key], ours)
        diff = first_diff(b.pop('digests'), c.pop('digests'))
        died = b['queen_death']
        pairs.append({
            'map': key[0], 'seed': key[1], 'side': key[2], 'first_diff_round': diff,
            'identity_ok': diff is None or (died is not None and diff >= died),
            'eligible': b['window_rounds'] >= MIN_WINDOW and b['hunter_rounds'] >= MIN_WINDOW,
            'base': b, 'candidate': c,
        })

    eligible = [p for p in pairs if p['eligible']]
    compared = closer = 0
    for p in eligible:
        b, c = p['base'], p['candidate']
        if c['mean_dist'] is None:
            # No hunt rounds with the switch on: counts as closer only if she was killed first.
            p['closer'] = True if c['foe_killed_in_hunt'] else None
        else:
            p['closer'] = c['mean_dist'] < b['mean_dist']
        if p['closer'] is not None:
            compared += 1
            closer += p['closer']

    def total(rows, tag, field):
        return sum(int(p[tag][field] or 0) for p in rows)

    def share(rows, tag):
        n = total(rows, tag, 'hunter_rounds')
        return round(total(rows, tag, 'near_rounds') / n, 3) if n else None

    def mean_dist(rows, tag):
        vals = [p[tag]['mean_dist'] for p in rows if p[tag]['mean_dist'] is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    identity_bad = [p for p in pairs if not p['identity_ok']]
    kills_b, kills_c = total(eligible, 'base', 'foe_killed_in_hunt'), total(eligible, 'candidate', 'foe_killed_in_hunt')
    enough = len(eligible) >= MIN_PAIRS
    approach = compared > 0 and 2 * closer > compared
    passed = not identity_bad and enough and approach and kills_c >= kills_b

    if identity_bad:
        note = (f'{len(identity_bad)} of {len(pairs)} pairs changed before our queen died, '
                'so the switch is not silent while she is alive.')
    elif not enough:
        note = (f'Not shown: only {len(eligible)} of {len(pairs)} pairs had our queen dead and theirs alive for '
                f'{MIN_WINDOW}+ rounds from round {HUNT_ROUND} (need {MIN_PAIRS}). All pairs were identical before our queen died.')
    else:
        note = (f'{len(eligible)} of {len(pairs)} pairs reached the hunt phase; hunters were closer to their queen in '
                f'{closer} of {compared}; she was killed in that phase {kills_c} times with the switch on vs {kills_b} without. '
                'All pairs were identical before our queen died.')

    result = {
        'passed': bool(passed), 'note': note,
        'pairs': len(pairs), 'identity_ok_pairs': len(pairs) - len(identity_bad),
        'queen_survived_pairs': sum(p['base']['queen_death'] is None for p in pairs),
        'eligible_pairs': len(eligible), 'compared_pairs': compared, 'closer_pairs': closer,
        'mean_hunter_dist': {'base': mean_dist(eligible, 'base'), 'candidate': mean_dist(eligible, 'candidate')},
        'near_share': {'base': share(eligible, 'base'), 'candidate': share(eligible, 'candidate')},
        'foe_queen_killed_in_hunt': {'base': kills_b, 'candidate': kills_c},
        'foe_queen_killed_head_on': {
            t: sum(1 for p in eligible if p[t]['foe_killed_in_hunt'] and p[t]['foe_death_reason'] == 'head-on')
            for t in ('base', 'candidate')},
        'small_deaths_in_hunt': {t: total(eligible, t, 'small_deaths_in_hunt') for t in ('base', 'candidate')},
        'end_only_their_queen': {t: total(pairs, t, 'end_only_their_queen') for t in ('base', 'candidate')},
        'end_both_dead': {t: total(pairs, t, 'end_both_dead') for t in ('base', 'candidate')},
        'settings': {'hunt_round': HUNT_ROUND, 'max_len': MAX_LEN, 'min_window': MIN_WINDOW,
                     'min_pairs': MIN_PAIRS, 'near': NEAR},
        'limits': 'Distances are grid distances with wrap, walls and portals ignored. Lengths come from replay '
                  'body tracking. The base and candidate games diverge after our queen dies, so later rounds '
                  'are not round-for-round comparable.',
        'games': pairs,
    }
    with open(a.output, 'w') as f:
        json.dump(result, f, indent=1)
    print(note)


if __name__ == '__main__':
    main()
