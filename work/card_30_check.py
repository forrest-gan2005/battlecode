#!/usr/bin/env python3
"""Card #30 big-map-trades mechanism check: with TRADE_CONTACT on, do our small dragons take even head-on swaps on
maps above 1,200 cells the way they already do on smaller maps?

usage: python3 work/card_30_check.py --replays DIRECTORY --base base --candidate candidate --output FILE
Reads kept replays DIRECTORY/<tag>_<map>_<seed>_<side>.replay and pairs them by (map, seed, side). Bot logs are not
needed (the batch drops them). Map size and walls come from the map inside each replay, never from its name.

Terms (the counting rule is the card's):
  head-on    one head moves into another head; both dragons die.
  ram        a head-on our dragon starts: it dies by head-on in its own turn and an enemy dragon dies with it.
  small      length 4 or less and not the queen (the queens are dragons 0 and 1).
  next to    at the start of the dragon's turn an enemy head is on a neighbouring cell with no kelp (wall) between;
             portal links are not counted.
  ram rate   rams / turns our small dragons start next to an enemy head, rounds 0-299.
  big map    more than 1,200 cells; small map: 1,200 cells or fewer (the bot's AGGRESSIVE_MAX_CELLS cut).
  view       the 7x7 square around its head that a dragon sees.
  the three swap checks, rebuilt from the replay at the start of such a turn:
             size         the target's parts in view against our length: at least our length (even rule), or at
                          least 5 and at least 2 more than ours (strict rule; the even rule at 59+ dragons);
             floor        8+ dragons on our team (strict rule only);
             outnumbered  enemy heads in view must not outnumber the other friendly heads in view (both rules).
  switch turn  a turn next to an enemy head on a big map where the even rule says yes and the strict rule says no:
             the turns this switch is meant to change.

Expectation, written before any game was run with the switch on (big pairs = pairs on big maps):
  1. target_seen: at least 30 switch turns over the big pairs, in the base games and in the candidate games;
  2. fires: the candidate rams in at least 80% of its switch turns;
  3. ram_rate: the candidate's pooled big-map ram rate is at least 10 points above the base's, and it is above the
     base's on at least two thirds of the big maps that have 20+ turns next to an enemy head in both configs;
  4. head_ons: we start more head-ons before round 300 (any length, sprints included) than the base, summed over
     big pairs and in at least two thirds of them;
  5. their_units: summed over big pairs, the opponent has fewer dragons at round 200 than in the base games;
  6. small_identical: every pair on a small map is replay-identical.
passed = all six (6 holds trivially when the run has no small map, and the note says so).
The thresholds were set after reading switch-off games only (the identity run, our base on both sides: big-map ram
rate 19% and 48 switch turns in 8 games, 3 of them rammed; small-map ram rate 31%; on maps of 601-1,200 cells, where
the even rule is live today, all 230 turns of the same kind ended in a ram). The card's 8% is against ladder teams,
so the gate is a rise in points and not a multiple.
Reported, not checked (the card's "what would show it's wrong" list, too noisy to gate at this size): our dragons
minus theirs at rounds 100 and 200, our total length at round 300, our queen's deaths before round 300, final lengths
and wins. Also reported: which of the three checks said no on declined turns, declined turns followed by an enemy ram
on that dragon within 2 rounds, queens killed by rams, first contact.
Not measurable here: play against opponents that ram on big maps (the local opponent is our own base, which does not),
the leader exclusion (a replay does not say who the leader is), transposed or mirrored copies of a map.

Exit code 0 when the measurement completed (even if passed is false); nonzero on missing or unreadable replays.
"""
import argparse, glob, hashlib, json, os, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# Copies of mybot2/main.cpp constants; used only to bucket games and to rebuild why a swap was declined.
BIG_CELLS = 1200        # AGGRESSIVE_MAX_CELLS
SMALL_LEN = 4           # TRADE_MAX_LENGTH
VIEW = 3                # Constants::VISION_RADIUS
FLOOR = 8               # TRADE_MIN_UNITS
STRICT_PARTS = 5        # TRADE_TARGET_MIN_PARTS
CAP_UNITS = 59          # min(unit limit 64, SPLIT_SOFT_LIMIT 60) - 1

LAST_ROUND = 300
SNAPS = (100, 200, 300)
CONTACT = 4
PUNISH_ROUNDS = 2
MIN_SWITCH = 30
FIRE_SHARE = 0.8
RATE_RISE = 0.10
MAP_MIN_TURNS = 20
MOST = 2 / 3
HEAD_ON = 3
CAUSES = ('wall', 'own_body', 'other_body', 'head_on', 'no_move')
ROUND_START, TURN_START, UPDATE, SPLIT, DEATH = (replay.EVENT_NAMES.index(n) for n in
                                                ('roundStart', 'turnStart', 'dragonUpdate', 'dragonSplit', 'dragonDeath'))
EXPECTATION = ("Written before any game was run with the switch on. Counting rule (the card's): rounds 0-299; small = "
               "length 4 or less and not the queen; next to = an enemy head on a neighbouring cell with no kelp between, "
               "portal links not counted; ram = the dragon dies by head-on in its own turn together with an enemy; ram "
               "rate = rams / turns our small dragons start next to an enemy head. Big map = more than 1,200 cells. "
               "Switch turn = such a turn on a big map where the small-map swap rule says yes (target at least our "
               "length in view, not outnumbered in view) and the big-map rule says no (target under 5 parts or less "
               "than 2 longer while we are under 59 dragons, or we are under 8 dragons). Expected on big maps: at "
               "least 30 switch turns in the base games and in the candidate games; the candidate rams in at least 80% "
               "of its switch turns; its pooled ram rate is at least 10 points above the base's and above the base's "
               "on at least two thirds of the big maps with 20+ such turns in both configs; we start more head-ons "
               "before round 300 than the base, summed and in at least two thirds of the big pairs; the opponent has "
               "fewer dragons at round 200 than in the base games. On maps of 1,200 cells or fewer every pair is "
               "replay-identical. Thresholds were set from switch-off games only (our base on both sides: big-map ram "
               "rate 19%, 48 switch turns in 8 games). Reported but not gating: our dragons minus theirs at rounds 100 "
               "and 200, our total length at round 300, our queen's deaths before round 300.")


def terrain(text):
    W = H = 0
    kind = {}
    for line in text.splitlines():
        q = line.split()
        if not q:
            continue
        if q[0] == 'MAP':
            W, H = int(q[1]), int(q[2])
        elif q[0] == 'EDGE':
            kind[int(q[1])] = int(q[2])
    if W <= 0 or H <= 0:
        raise ValueError('replay map has no size')
    row = 2 * (W + 1)
    nbr = {(x, y): [] for x in range(W) for y in range(H)}
    for y in range(H):
        for x in range(W):
            for other, k in (((x, (y - 1) % H), kind.get(y * row + x, 0)),
                             (((x - 1) % W, y), kind.get(y * row + W + 1 + x, 0))):
                if k == 0 and other != (x, y):
                    nbr[(x, y)].append(other)
                    nbr[other].append((x, y))
    return W, H, nbr


def scan(path, ours, toggled):
    root = replay.load(path).root()
    result = root.pointer(4)
    winner = ('A', 'B')[result.u16(6)] if result.u16(4) == 1 else None
    text = root.text(0)
    W, H, nbr = terrain(text)
    big = W * H > BIG_CELLS
    bodies, team_of = {}, {}
    for line in text.splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
    if ours not in team_of.values():
        raise ValueError(f'{path}: no dragons for team {ours}')
    theirs = 'B' if ours == 'A' else 'A'
    queen = {team_of[i]: i for i in (0, 1) if i in team_of}
    at_head = {b[0]: i for i, b in bodies.items()}
    units = {'A': 0, 'B': 0}
    for i in bodies:
        units[team_of[i]] += 1
    side = lambda team: 'us' if team == ours else 'them'
    blank = lambda: {'us': 0, 'them': 0}
    turns, rams, started, started_late, punished, ally_hits = blank(), blank(), blank(), blank(), blank(), blank()
    switch_turns, switch_rams = blank(), blank()
    blocked = {s: {'size': 0, 'floor': 0, 'outnumbered': 0, 'only_size': 0, 'only_floor': 0, 'only_outnumbered': 0,
                   'none': 0} for s in ('us', 'them')}
    off_rule = blank()                # rams the rebuilt checks would have refused (guard rule, or rebuild error)
    rammer_len = victim_len = 0
    queen_death = {}                  # team -> (round, cause, by enemy ram)
    declined = {}                     # dragon -> rounds it declined in
    snap = {}
    first_contact = None
    h = hashlib.sha1()
    rnd = 0
    cur = ctx = None
    dead = []                         # (id, reason, team, length) within the current turn

    def take(force=False):
        for r in SNAPS:
            if r not in snap and (force or rnd >= r):
                length = {'A': [], 'B': []}
                for i, b in bodies.items():
                    length[team_of[i]].append(len(b))
                snap[r] = {'units': units[ours], 'their_units': units[theirs], 'total': sum(length[ours]),
                           'their_total': sum(length[theirs]), 'longest': max(length[ours], default=0),
                           'their_longest': max(length[theirs], default=0), 'reached': not force}

    def contact():
        mine = [b[0] for i, b in bodies.items() if team_of[i] == ours]
        for i, b in bodies.items():
            if team_of[i] == ours:
                continue
            x, y = b[0]
            for mx, my in mine:
                dx, dy = abs(mx - x), abs(my - y)
                if min(dx, W - dx) + min(dy, H - dy) <= CONTACT:
                    return True
        return False

    def open_turn(did):
        body = bodies.get(did)
        if body is None or rnd >= LAST_ROUND:
            return None
        team = team_of[did]
        if len(body) > SMALL_LEN or did == queen.get(team):
            return None
        near = [at_head[c] for c in nbr[body[0]] if c in at_head and team_of[at_head[c]] != team]
        if not near:
            return None
        hx, hy = body[0]
        view = {((hx + dx) % W, (hy + dy) % H) for dx in range(-VIEW, VIEW + 1) for dy in range(-VIEW, VIEW + 1)}
        allies = enemies = 0
        for c in view:
            i = at_head.get(c)
            if i is not None and i != did:
                if team_of[i] == team:
                    allies += 1
                else:
                    enemies += 1
        parts = max(sum(1 for c in bodies[e] if c in view) for e in near)
        crowd = ['outnumbered'] if allies < enemies else []
        even = (['size'] if parts < len(body) else []) + crowd
        strict = even
        if big:
            need = len(body) if units[team] >= CAP_UNITS else max(STRICT_PARTS, len(body) + 2)
            strict = (['size'] if parts < need else []) + (['floor'] if units[team] < FLOOR else []) + crowd
        return {'team': team, 'fails': even if toggled and team == ours else strict,
                'switch': not even and bool(strict)}

    def close_turn():
        nonlocal rammer_len, victim_len
        if cur is None:
            return
        mover = next((d for d in dead if d[0] == cur and d[1] == HEAD_ON), None)
        hit = [d for d in dead if d[0] != cur and d[1] == HEAD_ON] if mover else []
        enemy = [d for d in hit if d[2] != mover[2]]
        if mover and enemy:
            s = side(mover[2])
            (started if rnd < LAST_ROUND else started_late)[s] += 1
            if s == 'us' and rnd < LAST_ROUND:
                rammer_len += mover[3]
                victim_len += enemy[0][3]
        elif mover and hit:
            ally_hits[side(mover[2])] += 1
        if ctx:
            s = side(ctx['team'])
            turns[s] += 1
            switch_turns[s] += ctx['switch']
            switch_rams[s] += bool(ctx['switch'] and mover and enemy)
            if mover and enemy:
                rams[s] += 1
                off_rule[s] += bool(ctx['fails'])
            else:
                declined.setdefault(cur, []).append(rnd)
                for f in ctx['fails']:
                    blocked[s][f] += 1
                if len(ctx['fails']) == 1:
                    blocked[s]['only_' + ctx['fails'][0]] += 1
                elif not ctx['fails']:
                    blocked[s]['none'] += 1

    for ev in root.pointer(3):
        which = ev.u16(0)
        if which not in (ROUND_START, TURN_START, UPDATE, SPLIT, DEATH):
            continue
        pl = ev.pointer(0)
        if which == ROUND_START:
            close_turn()
            cur = ctx = None
            dead = []
            rnd = pl.i32(0)
            h.update(f"r{rnd}".encode())
            take()
            if first_contact is None and contact():
                first_contact = rnd
        elif which == TURN_START:
            close_turn()
            cur = pl.i32(0)
            dead = []
            ctx = open_turn(cur)
        elif which == UPDATE:
            did = pl.i32(0)
            head, tail = replay.point(pl.pointer(0)), replay.point(pl.pointer(1))
            h.update(f"u{did}{head}{tail}".encode())
            body = bodies.setdefault(did, deque())
            if not body or body[0] != head:
                if body and at_head.get(body[0]) == did:
                    del at_head[body[0]]
                body.appendleft(head)
                at_head[head] = did
            while len(body) > 1 and body[-1] != tail:
                body.pop()
        elif which == SPLIT:
            parent, child = pl.i32(0), pl.i32(4)
            h.update(f"s{parent}{child}".encode())
            team = ('A', 'B')[pl.u16(8)]
            for i, cells in ((parent, pl.pointer(0)), (child, pl.pointer(1))):
                old = bodies.get(i)
                if old and at_head.get(old[0]) == i:
                    del at_head[old[0]]
                if i not in bodies:
                    units[team] += 1
                bodies[i] = deque(replay.point(p) for p in cells)
                team_of[i] = team
                if bodies[i]:
                    at_head[bodies[i][0]] = i
        elif which == DEATH:
            did = pl.i32(0)
            reason = pl.u16(4)
            h.update(f"d{did}{reason}".encode())
            body = bodies.pop(did, None)
            if body is None:
                continue
            team = team_of[did]
            units[team] -= 1
            if body and at_head.get(body[0]) == did:
                del at_head[body[0]]
            dead.append((did, reason, team, len(body)))
            rammed = reason == HEAD_ON and cur is not None and cur != did and team_of.get(cur) != team
            if rammed:
                punished[side(team)] += sum(1 for r in declined.get(did, ()) if rnd - r <= PUNISH_ROUNDS)
            if did == queen.get(team) and team not in queen_death:
                queen_death[team] = (rnd, CAUSES[reason] if reason < len(CAUSES) else 'unknown', rammed)
    close_turn()
    take(force=True)
    alive = lambda team: [len(b) for i, b in bodies.items() if team_of[i] == team]
    queen_len = lambda team: len(bodies[queen[team]]) if team in queen and queen[team] in bodies else 0
    out = {'cells': W * H, 'big': big, 'rounds': rnd, 'first_contact': first_contact,
           'turns': turns['us'], 'rams': rams['us'], 'their_turns': turns['them'], 'their_rams': rams['them'],
           'switch_turns': switch_turns['us'], 'switch_rams': switch_rams['us'],
           'their_switch_turns': switch_turns['them'], 'their_switch_rams': switch_rams['them'],
           'started': started['us'], 'their_started': started['them'],
           'started_300_on': started_late['us'], 'their_started_300_on': started_late['them'],
           'rammer_len': rammer_len, 'victim_len': victim_len,
           'declined_then_rammed': punished['us'], 'their_declined_then_rammed': punished['them'],
           'rams_checks_would_refuse': off_rule['us'], 'ally_head_ons': ally_hits['us'],
           'blocked': blocked['us'], 'their_blocked': blocked['them'],
           'queen_death': queen_death.get(ours, (None, None, False))[0],
           'queen_death_cause': queen_death.get(ours, (None, None, False))[1],
           'queen_rammed': bool(queen_death.get(ours, (None, None, False))[2]),
           'their_queen_death': queen_death.get(theirs, (None, None, False))[0],
           'their_queen_rammed': bool(queen_death.get(theirs, (None, None, False))[2]),
           'queen_end': queen_len(ours), 'their_queen_end': queen_len(theirs),
           'longest_end': max(alive(ours), default=0), 'their_longest_end': max(alive(theirs), default=0),
           'total_end': sum(alive(ours)), 'their_total_end': sum(alive(theirs)),
           'win': int(winner == ours), 'digest': h.hexdigest()}
    for r in SNAPS:
        for key, value in snap[r].items():
            out[f'{key}_{r}'] = value
    return out


def collect(directory, tag, toggled):
    out = {}
    for p in sorted(glob.glob(os.path.join(directory, f'{tag}_*.replay'))):
        stem = os.path.basename(p)[len(tag) + 1:-len('.replay')]
        m, seed, s = stem.rsplit('_', 2)
        if s not in ('0', '1'):
            raise ValueError(f'{p}: unexpected side')
        out[(m, seed, s)] = scan(p, 'A' if s == '0' else 'B', toggled)
    return out


def rate(rams, turns):
    return round(rams / turns, 4) if turns else None


def pct(value):
    return 'n/a' if value is None else f'{100 * value:.0f}%'


def tally(rows):
    total = lambda f: sum(x[f] for x in rows)
    blocked = {k: sum(x['blocked'][k] for x in rows) for k in ('size', 'floor', 'outnumbered', 'only_size', 'only_floor',
                                                                'only_outnumbered', 'none')}
    early = lambda f: sum(1 for x in rows if x[f] is not None and x[f] < LAST_ROUND)
    contacts = sorted(x['first_contact'] for x in rows if x['first_contact'] is not None)
    out = {'games': len(rows), 'turns': total('turns'), 'rams': total('rams'), 'ram_rate': rate(total('rams'), total('turns')),
           'their_turns': total('their_turns'), 'their_rams': total('their_rams'),
           'their_ram_rate': rate(total('their_rams'), total('their_turns')),
           'switch_turns': total('switch_turns'), 'switch_rams': total('switch_rams'),
           'switch_ram_rate': rate(total('switch_rams'), total('switch_turns')),
           'their_switch_turns': total('their_switch_turns'), 'their_switch_rams': total('their_switch_rams'),
           'started': total('started'), 'their_started': total('their_started'),
           'started_300_on': total('started_300_on'), 'their_started_300_on': total('their_started_300_on'),
           'rammer_len_mean': round(total('rammer_len') / total('started'), 2) if total('started') else None,
           'victim_len_mean': round(total('victim_len') / total('started'), 2) if total('started') else None,
           'declined': total('turns') - total('rams'), 'declined_blocked_by': blocked,
           'declined_then_rammed': total('declined_then_rammed'),
           'rams_checks_would_refuse': total('rams_checks_would_refuse'), 'ally_head_ons': total('ally_head_ons'),
           'queen_deaths_before_300': early('queen_death'), 'their_queen_deaths_before_300': early('their_queen_death'),
           'queen_rammed': total('queen_rammed'), 'their_queen_rammed': total('their_queen_rammed'),
           'queen_death_rounds': [x['queen_death'] for x in rows],
           'first_contact': contacts, 'no_contact_games': len(rows) - len(contacts),
           'games_ended_before_200': sum(1 for x in rows if not x['reached_200']),
           'queen_end': total('queen_end'), 'their_queen_end': total('their_queen_end'),
           'longest_end': total('longest_end'), 'their_longest_end': total('their_longest_end'),
           'total_end': total('total_end'), 'their_total_end': total('their_total_end'),
           'wins_not_a_verdict': total('win')}
    for r in SNAPS:
        for key in ('units', 'their_units', 'total', 'their_total'):
            out[f'{key}_{r}'] = total(f'{key}_{r}')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--replays', required=True)
    ap.add_argument('--base', required=True)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    if not os.path.isdir(a.replays):
        sys.exit(f'no replay directory: {a.replays}')
    base, cand = collect(a.replays, a.base, False), collect(a.replays, a.candidate, True)
    if not base or not cand:
        sys.exit('missing replays for base or candidate')
    if set(base) != set(cand):
        sys.exit(f'unpaired replays: {sorted(set(base) ^ set(cand))[:6]}')
    keys = sorted(base)
    big = [k for k in keys if base[k]['big']]
    small = [k for k in keys if not base[k]['big']]
    same = [k for k in keys if base[k]['digest'] == cand[k]['digest']]
    B = lambda ks: tally([base[k] for k in ks])
    C = lambda ks: tally([cand[k] for k in ks])
    bb, bc, sb, sc = B(big), C(big), B(small), C(small)
    per_map, rose, flat, thin = {}, [], [], []
    for m in sorted({k[0] for k in keys}):
        ks = [k for k in keys if k[0] == m]
        mb, mc = B(ks), C(ks)
        per_map[m] = {'cells': base[ks[0]]['cells'], 'big': base[ks[0]]['big'],
                      'identical_pairs': sum(k in same for k in ks), 'base': mb, 'candidate': mc}
        if base[ks[0]]['big']:
            if min(mb['turns'], mc['turns']) < MAP_MIN_TURNS:
                thin.append(m)
            elif mc['ram_rate'] > mb['ram_rate']:
                rose.append(m)
            else:
                flat.append(m)
    base_rate, cand_rate = bb['ram_rate'], bc['ram_rate']
    more = [k for k in big if cand[k]['started'] > base[k]['started']]
    checks = {'target_seen': min(bb['switch_turns'], bc['switch_turns']) >= MIN_SWITCH,
              'fires': bc['switch_turns'] > 0 and bc['switch_rams'] >= FIRE_SHARE * bc['switch_turns'],
              'ram_rate': cand_rate is not None and base_rate is not None and cand_rate >= base_rate + RATE_RISE
                          and bool(rose) and len(rose) >= MOST * (len(rose) + len(flat)),
              'head_ons': bool(big) and bc['started'] > bb['started'] and len(more) >= MOST * len(big),
              'their_units': bool(big) and bc['their_units_200'] < bb['their_units_200'],
              'small_identical': all(k in same for k in small)}
    passed = all(checks.values())
    gap = lambda t, r: t[f'units_{r}'] - t[f'their_units_{r}']
    wrong = []
    if gap(bc, 100) < gap(bb, 100) and gap(bc, 200) < gap(bb, 200):
        wrong.append('our dragons fell further behind theirs at rounds 100 and 200')
    if bc['total_300'] < bb['total_300']:
        wrong.append('our total length at round 300 is lower')
    if bc['queen_deaths_before_300'] > bb['queen_deaths_before_300']:
        wrong.append('our queen died before round 300 in more games')
    n = len(big)
    per = lambda value: f'{value / n:.1f}' if n else 'n/a'
    blk = lambda t: (f"target too short in view {t['declined_blocked_by']['size']}, fewer than 8 dragons "
                     f"{t['declined_blocked_by']['floor']}, outnumbered in view {t['declined_blocked_by']['outnumbered']}, "
                     f"none of the three {t['declined_blocked_by']['none']}")
    failed = [name for name, ok in checks.items() if not ok]
    note = (f"{len(keys)} pairs: {n} on maps above 1,200 cells, {len(small)} on smaller maps; {len(same)} replay-identical. "
            f"Big maps, rounds 0-299, our small dragons: turns next to an enemy head base {bb['turns']}, candidate "
            f"{bc['turns']}; rammed in base {bb['rams']} ({pct(base_rate)}), candidate {bc['rams']} ({pct(cand_rate)}); "
            f"the opponent (our base, switch off) rammed {pct(bb['their_ram_rate'])} and {pct(bc['their_ram_rate'])}. "
            f"Switch turns (small-map rule says yes, big-map rule says no): base {bb['switch_turns']} with "
            f"{bb['switch_rams']} rams, candidate {bc['switch_turns']} with {bc['switch_rams']} rams "
            f"({pct(bc['switch_ram_rate'])}). Rate above base on maps: {', '.join(rose) or 'none'}"
            + (f"; not above on: {', '.join(flat)}" if flat else '')
            + (f"; too few turns to compare on: {', '.join(thin)}" if thin else '')
            + f". Head-ons we started before round 300 per game: base {per(bb['started'])}, candidate {per(bc['started'])} "
            f"(theirs {per(bb['their_started'])} and {per(bc['their_started'])}), more than base in {len(more)} of {n} "
            f"pairs. Opponent dragons at round 200 per game: "
            f"base {per(bb['their_units_200'])}, candidate {per(bc['their_units_200'])}; ours: base {per(bb['units_200'])}, "
            f"candidate {per(bc['units_200'])}; at round 100 ours/theirs: base {per(bb['units_100'])}/"
            f"{per(bb['their_units_100'])}, candidate {per(bc['units_100'])}/{per(bc['their_units_100'])}. Our total length "
            f"at round 300 per game: base {per(bb['total_300'])}, candidate {per(bc['total_300'])}. Our queen dead before "
            f"round 300: base {bb['queen_deaths_before_300']}, candidate {bc['queen_deaths_before_300']} games; their "
            f"queen: base {bb['their_queen_deaths_before_300']}, candidate {bc['their_queen_deaths_before_300']}. Declined "
            f"turns and which check said no (a turn can fail several): base {bb['declined']} ({blk(bb)}); candidate "
            f"{bc['declined']} ({blk(bc)}). Declined turns followed by an enemy ram on that dragon within 2 rounds: base "
            f"{bb['declined_then_rammed']}, candidate {bc['declined_then_rammed']}. Small-map pairs identical: "
            f"{sum(k in same for k in small)} of {len(small)}" + ('' if small else ' (no small map in this run)') + '. '
            + ('All six pre-registered checks held.' if passed else 'Failed checks: ' + ', '.join(failed) + '.')
            + (' Signs the card lists as wrong (reported, not gating): ' + '; '.join(wrong) + '.' if wrong else
               ' None of the card\'s three wrong-signs showed (reported, not gating).')
            + ' The local opponent does not ram on big maps, so this says nothing about ladder teams that do.')
    result = {'passed': passed, 'note': note, 'expectation': EXPECTATION, 'checks': checks,
              'target_seen': checks['target_seen'], 'fires': checks['fires'],
              'mechanism_shown': passed, 'wrong_signs': wrong,
              'pairs': len(keys), 'identical_pairs': len(same), 'big_pairs': n, 'small_pairs': len(small),
              'big_pairs_more_head_ons': len(more),
              'big_maps_rate_rose': rose, 'big_maps_rate_not_rose': flat, 'big_maps_too_few_turns': thin,
              'big': {'base': bb, 'candidate': bc}, 'small': {'base': sb, 'candidate': sc}, 'per_map': per_map,
              'games': [{'map': k[0], 'seed': k[1], 'side': k[2], 'identical': k in same,
                         'base': {f: v for f, v in base[k].items() if f != 'digest'},
                         'candidate': {f: v for f, v in cand[k].items() if f != 'digest'}} for k in keys]}
    with open(a.output, 'w') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(note)


if __name__ == '__main__':
    main()
