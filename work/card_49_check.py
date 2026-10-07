#!/usr/bin/env python3
"""Card #49 leader-wait mechanism check (LEADER_WAIT): does the team keep eating after the round the leader rules
switch on, when the leader is still a small dragon?

usage: python3 work/card_49_check.py --replays DIR --base base --candidate candidate --output FILE
Replays are DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1), paired by (map, seed, side).

Words. The leader is the dragon the others feed late in the game. The leader rules protect it before feeding
starts: from the switch round (150 on maps above 1,200 cells, 300 on smaller ones) a dragon that takes itself for
the leader stops splitting, trading, harvesting and hunting, and the others leave the pearls within 9 tiles of it.
With LEADER_WAIT on, all of that waits until the leader is 10 long, as long as feeding has not started.

Everything is read from the replays alone (no bot logs):

  pearls         every time one of our dragons gets longer by stepping (one per tile of growth)
  before/after   the 50 rounds up to the switch round against the 50 rounds after it (the card's 101-150 against
                 151-200 on big maps)
  target game    a switch-off game in which our longest dragon is shorter than 10 when the switch round ends
  first change   the first round in which the switch-on game is not the same game as its switch-off pair
  waiting round  a round after the switch round (big maps: 151-300) in which our longest dragon is shorter than 10
                 and feeding has not started (we have fewer than 56 dragons once round 200 is past)
  near the leader  within 9 tiles (wrap-around street distance) of the head of our longest dragon

PASS RULE, fixed before any switch-on game was played. It is judged on the maps above 1,200 cells only; smaller
maps are reported the same way but never decide. passed = all of:

  target_seen   at least half of the switch-off games are target games
  inert_before  every pair is the same game in every round before the switch round
  changes_play  at least 3/4 of the target pairs have their first change within 50 rounds of the switch round
  eating        switch on, over the pairs that both reach 50 rounds past the switch round (at least half of the
                pairs must): pooled pearls after >= pooled pearls before, pooled pearls after > the switch-off
                games' pearls after, and the switch-on game eats more than its pair in more pairs than it eats fewer
  leader_kept   false only when our longest dragon is clearly shorter with the switch on, at round 300 (switch
                round + 150) or at the end: the average over the games is below 0.9 of the switch-off average AND it
                is shorter in more pairs than it is longer (two conditions, because 16 games are noisy)

fires_as_specified = inert_before and changes_play. "eating" and "leader_kept" are the card's own two tests: eating
still dropping means the leader rules are not the cause; eating back but a shorter leader means we traded the
leader for pearls. A pair is the same game up to the switch round, so "pearls before" is the same number for both
builds and the comparison is really about the 50 rounds after.

Reported without a threshold: splits (25 rounds before against 25 after), dragons alive, pearls and turns near the
leader, how often a dragon exactly 4 long splits, deaths of our longest dragon, the opponent's pearls, wins.

Known before the run, from switch-off games only (the 20 identity games on the old 10 maps, the release bot against
itself, each read from both sides): on the 2 maps above 1,200 cells 2 of 8 are target games, the teams average 56
dragons at round 150 and pearls after/before are 3450/3444 = 1.00, so the ladder's drop (0.74) does not show there;
on the 8 smaller maps 27 of 32 are target games at round 300 and pearls after/before are 3004/3522 = 0.85. In one
target game a dragon ate its way from 4 to 16 in seven rounds, so waiting can be over within a few rounds. Queen
games start feeding at round 301, which a replay does not show; on small maps the switch then has nothing to act on.
"""
import argparse, glob, hashlib, json, math, os, sys, concurrent.futures as cf
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# The bot's own numbers (mybot2/main.cpp).
BIG_CELLS = 1200     # AGGRESSIVE_MAX_CELLS
GROW_BIG = 150       # LEADER_GROW_ROUND_BIG
GROW_SMALL = 300     # LEADER_GROW_ROUND
MIN_LEN = 10         # LEADER_MIN_LEN
ZONE = 9             # LEADER_PEARL_RADIUS
FEED_ROUND = 400     # ENDGAME_ROUND
CAP_UNITS = 56       # FEED_CAP_UNITS
CAP_ROUND = 200      # FEED_CAP_ROUND
SPLIT_LEN = 4        # SPLIT_MIN_LENGTH

# The card's windows.
SPAN = 50
SPLIT_SPAN = 25
LATER = 150

# PASS RULE (fixed before seeing results)
TARGET_SHARE = 0.5
CHANGE_SHARE = 0.75
EAT_RATIO = 1.0
LEADER_KEEP = 0.9

CAUSE = ['wall', 'self', 'body', 'headon', 'none']


def gap(a, b, size):
    raw = abs(a - b)
    return min(raw, size - raw)


def one(job):
    path, side_tag = job
    ours = 'A' if side_tag == '0' else 'B'
    root = replay.load(path).root()
    text = root.text(0)
    W = H = 0
    bodies, team_of = {}, {}
    for line in text.splitlines():
        q = line.split()
        if not q:
            continue
        if q[0] == 'MAP':
            W, H = int(q[1]), int(q[2])
        elif q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
    if not W or not H or not bodies:
        raise ValueError(f'{os.path.basename(path)} carries no map size or no dragons')
    cells = W * H
    big = cells > BIG_CELLS
    G = GROW_BIG if big else GROW_SMALL
    wait_lo, wait_hi = G + 1, min(G + LATER, FEED_ROUND)
    result = root.pointer(4)
    winner = ('A', 'B')[result.u16(6)] if result.u16(4) == 1 else None

    c = Counter()
    pearls = {True: Counter(), False: Counter()}     # keyed by "ours"
    splits = {True: Counter(), False: Counter()}
    snaps = {}
    sig = {}
    hasher = hashlib.sha1()
    rnd = 0
    fed = False

    def team_state(mine):
        lens = [len(b) for d, b in bodies.items() if (team_of.get(d) == ours) == mine]
        return len(lens), max(lens, default=0), sum(lens)

    def longest_now(skip=None):
        """Longest length among our dragons and the heads of the dragons that long (skip = leave one dragon out)."""
        top, heads = 0, []
        for d, b in bodies.items():
            if d == skip or team_of.get(d) != ours or not b:
                continue
            if len(b) > top:
                top, heads = len(b), [b[0]]
            elif len(b) == top:
                heads.append(b[0])
        return top, heads

    def near(cell, heads):
        return any(gap(cell[0], h[0], W) + gap(cell[1], h[1], H) <= ZONE for h in heads)

    def waiting():
        return wait_lo <= rnd <= wait_hi and not fed

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        pl = ev.pointer(0)
        if kind == 'roundStart':
            sig[rnd] = hasher.hexdigest()[:16]
            hasher = hashlib.sha1()
            rnd = pl.i32(0)
            us, them = team_state(True), team_state(False)
            snaps[rnd] = (us, them)
            fed = rnd > FEED_ROUND or (rnd > CAP_ROUND and us[0] >= CAP_UNITS)
            if wait_lo <= rnd <= wait_hi:
                c['window_rounds'] += 1
                c['window_fed_rounds'] += fed
                c['wait_rounds'] += (not fed) and 0 < us[1] < MIN_LEN
        elif kind == 'dragonAction':
            did = pl.i32(0)
            if team_of.get(did) != ours or not bodies.get(did) or not waiting():
                continue
            top, heads = longest_now()
            if top >= MIN_LEN:
                continue
            a = pl.pointer(0)
            split = a is not None and a.u16(0) == 1
            mine = len(bodies[did])
            c['wait_turns'] += 1
            if mine == top:
                c['wait_longest_turns'] += 1
                c['wait_longest_splits'] += split
            else:
                c['wait_other_turns'] += 1
                c['wait_other_turns_near'] += near(bodies[did][0], heads)
            if mine == SPLIT_LEN:
                c['wait_len4_turns'] += 1
                c['wait_len4_splits'] += split
            c['wait_splits'] += split
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            head, tail = replay.point(pl.pointer(0)), replay.point(pl.pointer(1))
            hasher.update(f'u{did}{head}{tail}'.encode())
            b = bodies.setdefault(did, deque())
            before = len(b)
            moved = bool(b) and b[0] != head
            if not b or moved:
                b.appendleft(head)
            while len(b) > 1 and b[-1] != tail:
                b.pop()
            grown = len(b) - before if before > 0 and moved else 0
            if grown <= 0:
                continue
            mine = team_of.get(did) == ours
            pearls[mine][rnd] += grown
            if not mine or not waiting():
                continue
            top, heads = longest_now(skip=did)
            if max(top, before) >= MIN_LEN:
                continue
            c['wait_pearls'] += grown
            if before >= top:
                c['wait_longest_pearls'] += grown
            else:
                c['wait_other_pearls'] += grown
                c['wait_other_pearls_near'] += grown * near(head, heads)
                if len(heads) == 1:
                    c['wait_other_pearls_one_leader'] += grown
                    c['wait_other_pearls_near_one_leader'] += grown * near(head, heads)
        elif kind == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            hasher.update(f's{pa}{ch}'.encode())
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0))
            bodies[ch] = deque(replay.point(x) for x in pl.pointer(1))
            team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
            splits[team_of[pa] == ours][rnd] += 1
        elif kind == 'dragonDeath':
            did = pl.i32(0)
            r = pl.u16(4)
            hasher.update(f'd{did}{r}'.encode())
            if team_of.get(did) == ours and bodies.get(did) and wait_lo <= rnd <= wait_hi:
                top, _ = longest_now()
                if len(bodies[did]) == top:
                    c['longest_deaths'] += 1
                    c[f"longest_deaths_{CAUSE[r] if r < 5 else 'other'}"] += 1
                    c['longest_deaths_while_short'] += top < MIN_LEN and not fed
            bodies.pop(did, None)
    sig[rnd] = hasher.hexdigest()[:16]
    final = (team_state(True), team_state(False))

    def at(r):
        return snaps.get(r, final)

    def window(counter, lo, hi):
        return sum(counter[r] for r in range(lo, hi + 1))

    out = dict(c)
    out.update(cells=cells, big=big, switch_round=G, rounds=rnd, win=int(winner == ours),
               reached_after=int(rnd >= G + SPAN),
               pearls_before=window(pearls[True], G - SPAN + 1, G), pearls_after=window(pearls[True], G + 1, G + SPAN),
               their_pearls_before=window(pearls[False], G - SPAN + 1, G),
               their_pearls_after=window(pearls[False], G + 1, G + SPAN),
               splits_before=window(splits[True], G - SPLIT_SPAN, G - 1),
               splits_after=window(splits[True], G, G + SPLIT_SPAN - 1),
               alive_switch=at(G + 1)[0][0], alive_after=at(G + SPAN + 1)[0][0],
               longest_switch=at(G + 1)[0][1], longest_after=at(G + SPAN + 1)[0][1],
               longest_later=at(G + LATER)[0][1], longest_end=final[0][1],
               total_later=at(G + LATER)[0][2], total_end=final[0][2],
               their_longest_later=at(G + LATER)[1][1], their_longest_end=final[1][1],
               around={str(k): pearls[True][G + k] for k in range(-9, 11)},
               sig=[sig.get(r, '') for r in range(rnd + 1)])
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


def first_change(a, b):
    """First round in which two games differ, or None when they are the same game."""
    for r in range(max(len(a), len(b))):
        if (a[r] if r < len(a) else None) != (b[r] if r < len(b) else None):
            return r
    return None


def share(a, b):
    return a / b if b else 0.0


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


RAW = ['window_rounds', 'window_fed_rounds', 'wait_rounds', 'wait_turns', 'wait_longest_turns', 'wait_longest_splits',
       'wait_other_turns', 'wait_other_turns_near', 'wait_len4_turns', 'wait_len4_splits', 'wait_splits', 'wait_pearls',
       'wait_longest_pearls', 'wait_other_pearls', 'wait_other_pearls_near', 'wait_other_pearls_one_leader',
       'wait_other_pearls_near_one_leader', 'longest_deaths', 'longest_deaths_while_short']


def side_view(rows, both):
    """One build's numbers over a list of games; `both` marks the games whose pair reaches the after window."""
    s = Counter()
    for r in rows:
        s.update({k: r.get(k, 0) for k in RAW})
        for k in CAUSE + ['other']:
            s[f'longest_deaths_{k}'] += r.get(f'longest_deaths_{k}', 0)
    full = [r for r, ok in zip(rows, both) if ok]
    before, after = sum(r['pearls_before'] for r in full), sum(r['pearls_after'] for r in full)
    their_before, their_after = sum(r['their_pearls_before'] for r in full), sum(r['their_pearls_after'] for r in full)
    out = {'games': len(rows), 'wins': sum(r['win'] for r in rows),
           'games_longest_short_at_switch': sum(0 < r['longest_switch'] < MIN_LEN for r in rows),
           'pearls_before': before, 'pearls_after': after, 'pearls_after_over_before': round(share(after, before), 3),
           'their_pearls_before': their_before, 'their_pearls_after': their_after,
           'their_pearls_after_over_before': round(share(their_after, their_before), 3),
           'pearls_per_round_around_switch': {k: sum(r['around'][k] for r in full) for k in (full[0]['around'] if full else {})},
           'splits_before': sum(r['splits_before'] for r in full), 'splits_after': sum(r['splits_after'] for r in full),
           'alive_at_switch': round(mean(r['alive_switch'] for r in full), 2),
           'alive_50_rounds_later': round(mean(r['alive_after'] for r in full), 2),
           'longest_at_switch': round(mean(r['longest_switch'] for r in rows), 2),
           'longest_50_rounds_later': round(mean(r['longest_after'] for r in rows), 2),
           'longest_150_rounds_later': round(mean(r['longest_later'] for r in rows), 2),
           'longest_at_end': round(mean(r['longest_end'] for r in rows), 2),
           'total_150_rounds_later': round(mean(r['total_later'] for r in rows), 2),
           'total_at_end': round(mean(r['total_end'] for r in rows), 2),
           'their_longest_150_rounds_later': round(mean(r['their_longest_later'] for r in rows), 2),
           'their_longest_at_end': round(mean(r['their_longest_end'] for r in rows), 2),
           'waiting': {k[5:] if k.startswith('wait_') else k: s[k] for k in RAW},
           'longest_deaths_by_cause': {k: s[f'longest_deaths_{k}'] for k in CAUSE + ['other'] if s[f'longest_deaths_{k}']}}
    out['splits_after_over_before'] = round(share(out['splits_after'], out['splits_before']), 3)
    out['waiting']['other_pearls_near_share'] = round(share(s['wait_other_pearls_near'], s['wait_other_pearls']), 4)
    out['waiting']['other_pearls_near_share_one_leader'] = round(
        share(s['wait_other_pearls_near_one_leader'], s['wait_other_pearls_one_leader']), 4)
    out['waiting']['other_pearls_near_per_100_turns_near'] = round(
        100 * share(s['wait_other_pearls_near'], s['wait_other_turns_near']), 2)
    out['waiting']['len4_split_share'] = round(share(s['wait_len4_splits'], s['wait_len4_turns']), 4)
    out['waiting']['pearls_per_100_turns'] = round(100 * share(s['wait_pearls'], s['wait_turns']), 2)
    return out


def group_view(keys, base, cand):
    """Paired numbers for one map group (all above 1,200 cells, or all at or below)."""
    if not keys:
        return None
    G = base[keys[0]]['switch_round']
    change = {k: first_change(base[k]['sig'], cand[k]['sig']) for k in keys}
    target = [k for k in keys if 0 < base[k]['longest_switch'] < MIN_LEN]
    both = [bool(base[k]['reached_after'] and cand[k]['reached_after']) for k in keys]
    bv = side_view([base[k] for k in keys], both)
    cv = side_view([cand[k] for k in keys], both)
    early = [k for k in keys if change[k] is not None and change[k] < G]
    soon = [k for k in target if change[k] is not None and change[k] <= G + SPAN]
    full = [k for k, ok in zip(keys, both) if ok]

    def paired(field, pool):
        return {'shorter': sum(cand[k][field] < base[k][field] for k in pool),
                'same': sum(cand[k][field] == base[k][field] for k in pool),
                'longer': sum(cand[k][field] > base[k][field] for k in pool)}

    more = {'fewer': sum(cand[k]['pearls_after'] < base[k]['pearls_after'] for k in full),
            'same': sum(cand[k]['pearls_after'] == base[k]['pearls_after'] for k in full),
            'more': sum(cand[k]['pearls_after'] > base[k]['pearls_after'] for k in full)}
    later, end = paired('longest_later', keys), paired('longest_end', keys)
    hit = [k for k in full if k in set(target)]
    target_only = {'pairs': len(hit), 'pearls_before': sum(base[k]['pearls_before'] for k in hit),
                   'base_pearls_after': sum(base[k]['pearls_after'] for k in hit),
                   'candidate_pearls_after': sum(cand[k]['pearls_after'] for k in hit)}
    rule = {
        'target_seen': len(target) >= math.ceil(TARGET_SHARE * len(keys)),
        'inert_before': not early,
        'changes_play': bool(target) and len(soon) >= CHANGE_SHARE * len(target),
        'eating': (2 * len(full) >= len(keys) and cv['pearls_after'] >= EAT_RATIO * cv['pearls_before']
                   and cv['pearls_after'] > bv['pearls_after'] and more['more'] > more['fewer']),
        'leader_kept': not (
            (cv['longest_150_rounds_later'] < LEADER_KEEP * bv['longest_150_rounds_later'] and later['shorter'] > later['longer'])
            or (cv['longest_at_end'] < LEADER_KEEP * bv['longest_at_end'] and end['shorter'] > end['longer'])),
    }
    rule = {k: bool(v) for k, v in rule.items()}
    drop = bv['pearls_before'] - bv['pearls_after']
    return {'switch_round': G, 'pairs': len(keys), 'maps': sorted({k[0] for k in keys}),
            'target_pairs': len(target), 'pairs_changed_before_switch': len(early),
            'target_pairs_changed_within_50_rounds': len(soon),
            'pairs_never_changed': sum(v is None for v in change.values()),
            'first_change_rounds': sorted(v for v in change.values() if v is not None),
            'pairs_reaching_after_window': len(full),
            'base_drop_seen': bv['pearls_after'] < bv['pearls_before'],
            'drop_recovered_share': round(share(cv['pearls_after'] - bv['pearls_after'], drop), 3) if drop > 0 else None,
            'pairs_pearls_after': more, 'target_pairs_only': target_only,
            'pairs_longest_150_rounds_later': later, 'pairs_longest_at_end': end,
            'pass_rule': rule, 'base': bv, 'candidate': cv}


def tell(g):
    """One group's reading in plain words."""
    b, c, r = g['base'], g['candidate'], g['pass_rule']
    G = g['switch_round']
    bw, cw = b['waiting'], c['waiting']
    hit = g['target_pairs_only']
    later, end = g['pairs_longest_150_rounds_later'], g['pairs_longest_at_end']
    return (f"{g['pairs']} pairs, leader rules from round {G + 1}. "
            f"Target games (switch off, our longest shorter than {MIN_LEN} when round {G} ends): {g['target_pairs']}/{g['pairs']}. "
            f"Pairs that are the same game before round {G}: {g['pairs'] - g['pairs_changed_before_switch']}/{g['pairs']}. "
            f"Target pairs whose first change comes within {SPAN} rounds: "
            f"{g['target_pairs_changed_within_50_rounds']}/{g['target_pairs']} ({g['pairs_never_changed']} of all pairs never change). "
            f"Our pearls in the {SPAN} rounds after against the {SPAN} before ({g['pairs_reaching_after_window']} pairs get that far): "
            f"switch off {b['pearls_after']} against {b['pearls_before']} = {b['pearls_after_over_before']:.2f}, "
            f"switch on {c['pearls_after']} against {c['pearls_before']} = {c['pearls_after_over_before']:.2f}; "
            f"the switch-on game eats more than its pair in {g['pairs_pearls_after']['more']} pairs and fewer in "
            f"{g['pairs_pearls_after']['fewer']}; target pairs alone ({hit['pairs']}): {hit['base_pearls_after']} -> "
            f"{hit['candidate_pearls_after']} after, {hit['pearls_before']} before. "
            + ('' if g['base_drop_seen'] else "The switch-off games show no drop here, so 'no drop' with the switch on says "
               'little by itself; the comparison with the pair is what counts. ')
            + f"The opponent (always switch off): {b['their_pearls_after_over_before']:.2f} and "
            f"{c['their_pearls_after_over_before']:.2f}. "
            f"Our longest dragon {LATER} rounds after round {G}: {b['longest_150_rounds_later']} -> {c['longest_150_rounds_later']} "
            f"on average (shorter in {later['shorter']} pairs, longer in {later['longer']}); at the end: {b['longest_at_end']} -> "
            f"{c['longest_at_end']} (shorter in {end['shorter']}, longer in {end['longer']}). "
            f"Not part of the rule: splits in the {SPLIT_SPAN} rounds from round {G} against the {SPLIT_SPAN} before "
            f"{b['splits_after']}/{b['splits_before']} = {b['splits_after_over_before']:.2f} -> "
            f"{c['splits_after']}/{c['splits_before']} = {c['splits_after_over_before']:.2f}; dragons alive {SPAN} rounds later "
            f"against the switch round {b['alive_50_rounds_later']}/{b['alive_at_switch']} -> "
            f"{c['alive_50_rounds_later']}/{c['alive_at_switch']}; waiting rounds {bw['rounds']} -> {cw['rounds']}, and in them: "
            f"pearls per 100 dragon turns {bw['pearls_per_100_turns']} -> {cw['pearls_per_100_turns']}, the other dragons' "
            f"pearls eaten near the leader {bw['other_pearls_near']}/{bw['other_pearls']} = {bw['other_pearls_near_share']:.1%} -> "
            f"{cw['other_pearls_near']}/{cw['other_pearls']} = {cw['other_pearls_near_share']:.1%}, turns on which a dragon "
            f"exactly {SPLIT_LEN} long splits {bw['len4_splits']}/{bw['len4_turns']} -> {cw['len4_splits']}/{cw['len4_turns']}, "
            f"deaths of our longest dragon while it is shorter than {MIN_LEN} {bw['longest_deaths_while_short']} -> "
            f"{cw['longest_deaths_while_short']}; wins {b['wins']} -> {c['wins']}. "
            + 'Rule: ' + ', '.join(f"{k} {'yes' if v else 'NO'}" for k, v in r.items()) + '.')


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
    for k in keys:
        if base[k]['cells'] != cand[k]['cells']:
            sys.exit(f'pair {k} was played on two different maps')
    big = group_view([k for k in keys if base[k]['big']], base, cand)
    small = group_view([k for k in keys if not base[k]['big']], base, cand)
    if big is None:
        sys.exit(f'no pair on a map above {BIG_CELLS} cells; the pass rule cannot be measured')
    rule = big['pass_rule']
    fires = rule['inert_before'] and rule['changes_play']
    passed = all(rule.values())
    if not rule['target_seen']:
        reading = (f"target not seen: our longest dragon was already {MIN_LEN} or longer at the switch round in most "
                   'switch-off games, so the switch had little to act on')
    elif not fires:
        reading = 'the switch did not change play the way the code says it should; treat this as a build problem'
    elif not rule['eating']:
        reading = ('the switch fires, but eating still drops after the switch round (or is not above the switch-off '
                   "games); by the card's own test the leader rules are then not the cause")
    elif not rule['leader_kept']:
        reading = ("the switch fires and eating is back, but our longest dragon is clearly shorter; by the card's own "
                   'test we traded the leader for pearls')
    else:
        reading = 'the switch fires, eating does not drop after the switch round, and our longest dragon is not clearly shorter'
    note = (f"Maps above {BIG_CELLS} cells: " + tell(big) + ' Reading: ' + reading + '.'
            + (f" Maps at or below {BIG_CELLS} cells (reported, never decide): " + tell(small) if small else
               f" Maps at or below {BIG_CELLS} cells (leader rules from round {GROW_SMALL + 1}): not in this run, not measured."))
    agree = None if small is None else bool(small['pass_rule']['eating'] and small['pass_rule']['leader_kept'])
    out = {'passed': bool(passed), 'note': note, 'target_seen': rule['target_seen'], 'fires_as_specified': bool(fires),
           'eating_shown': rule['eating'], 'leader_kept': rule['leader_kept'], 'small_maps_agree': agree, 'pairs': len(keys),
           'maps': sorted({k[0] for k in keys}),
           'pass_rule': {'target_share': TARGET_SHARE, 'change_share': CHANGE_SHARE, 'eat_ratio': EAT_RATIO,
                         'leader_keep': LEADER_KEEP, 'min_len': MIN_LEN, **rule},
           'big_maps': big, 'small_maps': small,
           'limits': ('read from replays without bot logs: "our longest dragon" stands in for the leader, but each dragon '
                      'only knows the leader it has heard of (reports up to 25 rounds old, sightings count the parts in '
                      'view), so "near the leader" and "waiting round" are approximations and the switch can act in a '
                      'game that is not a target game; feeding is taken to start at round 401, or with 56 dragons after '
                      'round 200, and the earlier start in queen games (round 301) is not visible in a replay, which is '
                      'why waiting rounds stop at round 300 on big maps and are unreliable on small maps; a game that '
                      'ends early keeps its last lengths for the later readings; pairs are the same game until the '
                      'first change, after that the two games drift apart and single-pair differences are noise; '
                      'lengths, splits, deaths and wins are raw counts from a small sample, not evidence of an outcome')}
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
        sys.exit(f'card 49 check failed: {exc}')
