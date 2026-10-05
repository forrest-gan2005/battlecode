#!/usr/bin/env python3
"""Card #31 mechanism check (QH_SCOUT): the first small dragon to see their queen hunts her and shares her
position by sonar; once our queen is dead (from round 100) every small non-leader with a fresh position hunts.

usage: python3 work/card_31_check.py --replays DIR --base base --candidate candidate --output FILE
Reads paired replays DIR/<tag>_<map>_<seed>_<side>.replay (side 0 = we are team A).

Words:
  small        id above 1 and length <= MAX_LEN (the bot also skips a dragon that believes it is our longest).
  queen ping   our sonar message with a hunter id and her cell, read with the codec key. A hunter pings every
               turn while it hunts, so "who pings" is "who hunts".
  early        our queen is alive, or the round is below REVENGE_ROUND.
  revenge      round >= REVENGE_ROUND with our queen dead and theirs alive (replay truth, not the bot's belief).
  walk         steps on the real map without using any portal (kelp blocks, dragon bodies ignored).
  sighting     the same small dragon of ours has her head inside its 7x7 view at the end of two rounds in a row.
  opportunity  a sighting where that dragon also has a walk to her head. (Attempt 1 counted every sighting. The
               revised build only starts a hunt when she can be walked to or a sure portal leads to her, so a
               dragon looking at her across kelp is no longer expected to go.)
  hunter turn  a turn in which the dragon sends a queen ping. The ping carries the cell the hunter is heading for.
  crossing     a hunter turn in which the hunter's head goes through a portal. It is "closer" when the tile it
               lands on has a shorter walk to the pinged cell than the tile it left (no walk at all counts as
               longest), "boxed" when it was not closer but every plain step off its tile led onto a dragon body
               (the bot then takes any portal rather than die), and "stray" otherwise.
  portal chance  a hunter turn that starts on a tile with a portal on one of its sides.

Expectation 1-12, written before any switch-on game was run (attempt 1; only the word "opportunity" in 2-3
was narrowed for attempt 2, as said above):
  1. silent: a pair is replay-identical up to the round of the first queen ping.
  2. target seen: at least MIN_GAMES switch-on games have an opportunity after round QUIET.
  3. scout fires: in at least FIRE_SHARE of those games a queen ping is sent within FIRE_WAIT rounds of the
     first opportunity.
  4. one early hunter: over the early rounds with a queen ping, the mean number of dragons pinging is <= ONE_MAX.
  5. follows: in at least half of the early hunter-rounds the hunter is within NEAR cells of her head.
  6. not wasted: at most half of the early hunters die while hunting without ever getting next to her.
  7. small cost: before round 300, early hunting takes at most HUNT_SHARE of our dragon-rounds.
  8. no false alarm: our dragons never send "our queen is dead" while she is alive.
  9. revenge seen: at least MIN_REVENGE switch-on games have MIN_WINDOW+ revenge rounds.
 10. revenge trigger: "our queen is dead" is sent in at least TRIGGER_SHARE of those games.
 11. revenge hunt: in more than half of the triggered revenge games a dragon pings her inside the window.
 12. traffic: our sonar messages are <= COST_RATIO of the base count and we time out no more often
     (and CPU points per action are <= COST_RATIO of base when the replay records them).
Expectation 13-14, added for Zhe's revision (a hunter takes a portal only when it is sure the far tile is closer
to her last seen cell) before any game of the revised build was run:
 13. portal seen: at least PORTAL_GAMES switch-on games have a portal chance, PORTAL_CHANCES or more in total.
 14. portal rule: no stray crossing.
passed = all fourteen. A check whose target never appeared is null and never counts as a pass.
Her deaths, kills by hunters, wins, lengths, how often a hunter has a walk to her and the closer/boxed crossing
counts are reported but not gated: 16-32 games cannot settle them.
Exit code 0 for a completed measurement, nonzero for missing or unpaired replays.
"""
import argparse, concurrent.futures as cf, glob, hashlib, json, os, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

MAX_LEN = 4
REVENGE_ROUND = 100
QUIET = 20
VIEW = 3
MIN_GAMES = 4
FIRE_SHARE = 2 / 3
FIRE_WAIT = 3
ONE_MAX = 1.5
NEAR = 6
HUNT_SHARE = 0.1
MIN_REVENGE = 3
MIN_WINDOW = 20
TRIGGER_SHARE = 1 / 3
COST_RATIO = 1.25
PORTAL_GAMES = 3
PORTAL_CHANCES = 10
MARKS = (100, 200, 300)
REASONS = ['wall', 'self', 'body', 'head-on', 'no action']
STEP = {'N': (0, -1), 'E': (1, 0), 'S': (0, 1), 'W': (-1, 0)}
BUILT_AS = (
    "How Zhe's answers were built. Small = not our queen, not the leader by the bot's own test, length 4 or less "
    "(answer 1 says longer than 4 is long, answer 4 says under 4: we took 4 or less). A small dragon that sees her "
    "after round 20 and has heard no queen ping for 20 rounds becomes the hunter: it walks to her, rams her head "
    "when in reach, and sends its id + her cell in all four directions every turn. Nobody else shares her position. "
    "A hunter stops when it reaches her last cell and she is gone, when its sighting is 20 rounds old, or when "
    "known walls seal her off. Not asked by Zhe, our choice: if two hunters hear each other before the revenge "
    "phase, the higher id stands down. Revenge phase = a dragon has been told our queen is dead and the round is "
    "100 or more: every small dragon holding a position at most 20 rounds old hunts and pings; longer dragons and "
    "the leader never do. 'Our queen is dead' comes from a dragon that saw her head one turn and an unexplained "
    "pearl there the next (card #17's trigger), passed on in two spare bits of the usual leader message. "
    "Revision asked by Zhe after the online games: a hunting dragon takes a portal only when it has seen both "
    "ends and the tile on the far side is surely closer to her last seen cell than the tile it stands on. "
    "'Surely closer' as built: the walk from the far tile to her cell over sides the dragon has seen open is "
    "shorter than the best possible walk from where it stands (unseen sides counted as open); walks use no "
    "portal. Other portals are shut for a hunter: it does not step through them, plan a route through them or "
    "scout them, and it only starts or keeps hunting when her cell can be walked to or such a portal on its side "
    "leads there. Our choice, not asked by Zhe: a hunter with no free step left still takes a portal rather "
    "than die.")

# mybot2/sonar_codec.hpp in Python: the check reads our own messages.
M64 = (1 << 64) - 1
SECRET = 0xE1DE70530C48DE42
CHECK_MASK = 0xFF << 55
TAG_MASK = 0x3 << 53
CIPHER_MASK = M64 & ~(CHECK_MASK | TAG_MASK)
PING_KIND = 0x2B5


def rotl(x, b):
    return ((x << b) | (x >> (64 - b))) & M64


def prf(key, m):
    k0, k1 = key
    v = [k0 ^ 0x736F6D6570736575, k1 ^ 0x646F72616E646F6D, k0 ^ 0x6C7967656E657261, k1 ^ 0x7465646279746573]

    def rounds(n):
        for _ in range(n):
            v[0] = (v[0] + v[1]) & M64
            v[1] = rotl(v[1], 13) ^ v[0]
            v[0] = rotl(v[0], 32)
            v[2] = (v[2] + v[3]) & M64
            v[3] = rotl(v[3], 16) ^ v[2]
            v[0] = (v[0] + v[3]) & M64
            v[3] = rotl(v[3], 21) ^ v[0]
            v[2] = (v[2] + v[1]) & M64
            v[1] = rotl(v[1], 17) ^ v[2]
            v[2] = rotl(v[2], 32)

    tail = 8 << 56
    v[3] ^= m
    rounds(2)
    v[0] ^= m
    v[3] ^= tail
    rounds(2)
    v[0] ^= tail
    v[2] ^= 0xFF
    rounds(4)
    return v[0] ^ v[1] ^ v[2] ^ v[3]


assert prf((0x0706050403020100, 0x0F0E0D0C0B0A0908), 0x0706050403020100) == 0x93F5F5799A932462


def make_key(width, height, tag):
    root = (SECRET, rotl(SECRET, 29) ^ 0xA5A5A5A5A5A5A5A5)
    game = (width << 40) | (height << 16) | (tag & 0x3)
    return prf(root, game), prf(root, game | (1 << 63))


def team_tag(team):
    return 0x2 if team == 'A' else 0x1


def seal(key, plain):
    plain &= M64 & ~CHECK_MASK
    check = prf(key, plain) & 0xFF
    return (plain ^ (prf(key, CHECK_MASK | check) & CIPHER_MASK)) | (check << 55)


def unseal(key, wire, streams):
    """Plain message, or None when the keyed check fails."""
    check = (wire & CHECK_MASK) >> 55
    if check not in streams:
        streams[check] = prf(key, CHECK_MASK | check) & CIPHER_MASK
    plain = (wire & (M64 & ~CHECK_MASK)) ^ streams[check]
    return plain if (prf(key, plain & (M64 & ~CHECK_MASK)) & 0xFF) == check else None


def pack_leader(tag, did, length, when, x, y, face=0, state=0):
    sized = min(length, 0x3FF) | ((state & 0x3) << 10)
    return ((did & 0xFFFF) | (sized << 16) | ((when & 0x1FF) << 28) | ((x & 0x7F) << 37) | ((y & 0x7F) << 44) |
            ((face & 0x3) << 51) | ((tag & 0x3) << 53))


def pack_ping(tag, hunter, cell, when, dead=0, state=0):
    return ((cell & 0x3FFF) | ((when & 0x1FF) << 14) | ((dead & 1) << 23) | ((state & 0x3) << 24) |
            ((hunter & 0xFFFF) << 26) | (PING_KIND << 42) | ((tag & 0x3) << 53) | (1 << 63))


def parse(plain):
    """Leader message (its top two length bits carry the 'our queen is dead' state) or queen ping; else 'other'."""
    body = plain & ((1 << 55) - 1)
    if plain >> 63 == 0:
        return {'kind': 'leader', 'id': body & 0x7FFF, 'state': (body >> 26) & 0x3, 'len': (body >> 16) & 0x3FF,
                'when': (body >> 28) & 0x1FF, 'x': (body >> 37) & 0x7F, 'y': (body >> 44) & 0x7F}
    if (body >> 42) & 0x7FF == PING_KIND:
        return {'kind': 'ping', 'cell': body & 0x3FFF, 'when': (body >> 14) & 0x1FF, 'dead': (body >> 23) & 1,
                'state': (body >> 24) & 0x3, 'id': (body >> 26) & 0xFFFF}
    return {'kind': 'other', 'state': 0}


def scan(path, ours):
    """One pass over a replay for our side."""
    root = replay.load(path).root()
    text = root.text(0)
    W, H = map(int, text.splitlines()[0].split()[1:3])
    result = root.pointer(4)
    winner = ('A', 'B')[result.u16(6)] if result.u16(4) == 1 else None
    bodies, team_of, edges = {}, {}, {}
    for line in text.splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
        elif q and q[0] == 'EDGE':
            edges[int(q[1])] = int(q[2])
    span = 2 * (W + 1)

    def side(cell, ch):
        """0 open, 1 kelp, 2 portal on that side of the tile. Map files may list a border side twice."""
        x, y = cell
        if ch == 'S':
            y, ch = (y + 1) % H, 'N'
        elif ch == 'E':
            x, ch = (x + 1) % W, 'W'
        if ch == 'N':
            ids = [y * span + x] + ([H * span + x] if y == 0 else [])
        else:
            ids = [y * span + W + 1 + x] + ([y * span + W + 1 + W] if x == 0 else [])
        return max(edges.get(i, 0) for i in ids)

    def beside(cell, ch):
        return (cell[0] + STEP[ch][0]) % W, (cell[1] + STEP[ch][1]) % H

    def walk_from(cell):
        """Steps from `cell` to every tile it can walk to without a portal."""
        dist, queue = {cell: 0}, deque([cell])
        while queue:
            c = queue.popleft()
            for ch in STEP:
                n = beside(c, ch)
                if n not in dist and side(c, ch) == 0:
                    dist[n] = dist[c] + 1
                    queue.append(n)
        return dist

    def boxed(cell):
        """Every plain step off this tile leads onto a dragon body (the bot's own test for 'no free step')."""
        taken = {c for b in bodies.values() for c in b}
        return not any(side(cell, ch) == 0 and beside(cell, ch) not in taken for ch in STEP)

    # Tiles with the same label can be walked between without a portal.
    region = {}
    for y in range(H):
        for x in range(W):
            if (x, y) not in region:
                region.update(dict.fromkeys(walk_from((x, y)), (x, y)))

    queens = [i for i in (0, 1) if team_of.get(i) == ours]
    foes = [i for i in (0, 1) if i in team_of and team_of[i] != ours]
    if len(queens) != 1 or len(foes) != 1:
        raise ValueError(f'{path}: ids 0 and 1 are not one queen per team')
    q_us, q_them = queens[0], foes[0]
    tag = team_tag(ours)
    key, streams, opened = make_key(W, H, tag), {}, {}

    def gap(a, b):
        dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
        return min(dx, W - dx), min(dy, H - dy)

    digests, h = {}, hashlib.sha1()
    death = {}
    hunters = {}
    early_ids, rev_ids = {}, {}
    opp_rounds, sight_rounds, in_view = [], [], set()
    marks = {}
    stat = {'sonar': 0, 'unreadable': 0, 'pings': 0, 'notices': 0, 'claims': 0, 'false_claims': 0, 'points': 0,
            'actions': 0, 'points_max': 0, 'tle': 0, 'window': 0, 'window_hunt': 0, 'ping_age': 0, 'ping_count': 0,
            'dragon_rounds': 0, 'walk_rounds': 0, 'walk_ok': 0}
    first = {'ping': None, 'claim': None}
    early_d, rev_d = [], []
    turn_start, hunt_turns, crossings = {}, {}, []
    rnd = 0

    def sample(hid):
        """Distance from a pinging hunter to her head, at ping time and at the end of the round."""
        if hid in bodies and q_them in bodies and team_of.get(hid) == ours:
            d = sum(gap(bodies[hid][0], bodies[q_them][0]))
            rec = hunters[hid]
            rec['min_dist'] = d if rec['min_dist'] is None else min(rec['min_dist'], d)
            return d
        return None

    def close_round():
        nonlocal in_view
        mine = {i: len(b) for i, b in bodies.items() if team_of.get(i) == ours}
        theirs = [len(b) for i, b in bodies.items() if team_of.get(i) != ours]
        seeing = set()
        if q_them in bodies:
            her = bodies[q_them][0]
            seeing = {i for i, n in mine.items() if i > 1 and n <= MAX_LEN and max(gap(bodies[i][0], her)) <= VIEW}
            again = seeing & in_view
            if again:
                sight_rounds.append(rnd)
            if any(region[bodies[i][0]] == region[her] for i in again):
                opp_rounds.append(rnd)
            for ids, out in ((early_ids, early_d), (rev_ids, rev_d)):
                for hid in ids.get(rnd, ()):
                    d = sample(hid)
                    if d is not None:
                        out.append(d)
                        stat['walk_rounds'] += 1
                        stat['walk_ok'] += region[bodies[hid][0]] == region[her]
            if rnd >= REVENGE_ROUND and q_us not in bodies:
                stat['window'] += 1
                stat['window_hunt'] += bool(rev_ids.get(rnd))
        in_view = seeing
        if rnd < 300:
            stat['dragon_rounds'] += len(mine)
        if rnd in MARKS:
            marks[rnd] = {'total_us': sum(mine.values()), 'units_us': len(mine),
                          'longest_us': max(mine.values(), default=0), 'total_them': sum(theirs),
                          'longest_them': max(theirs, default=0), 'queen_alive': q_us in bodies}
        digests[rnd] = h.hexdigest()

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else '?'
        pl = ev.pointer(0)
        if kind == 'roundStart':
            if rnd:
                close_round()
            rnd = pl.i32(0)
            h = hashlib.sha1()
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            head, tail = replay.point(pl.pointer(0)), replay.point(pl.pointer(1))
            h.update(f'u{did}{head}{tail}'.encode())
            body = bodies.setdefault(did, deque())
            if body and body[0] != head and team_of.get(did) == ours:
                left = body[0]
                if not any(side(left, ch) == 0 and beside(left, ch) == head for ch in STEP):
                    if not any(side(left, ch) == 2 for ch in STEP):
                        raise ValueError(f'{path}: round {rnd} dragon {did} went {left} -> {head} through no open '
                                         f'side and no portal; the map edges are not read correctly')
                    crossings.append({'id': did, 'round': rnd, 'from': left, 'to': head, 'boxed': boxed(left)})
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
            death[did] = (rnd, REASONS[reason] if reason < len(REASONS) else '?')
            bodies.pop(did, None)
        elif kind == 'dragonAction':
            if team_of.get(pl.i32(0)) == ours:
                if pl.i32(0) in bodies:
                    turn_start[pl.i32(0)] = (rnd, bodies[pl.i32(0)][0])
                usage = pl.pointer(1)
                points = usage.u64(0) if usage else 0
                stat['actions'] += 1
                stat['points'] += points
                stat['points_max'] = max(stat['points_max'], points)
                stat['tle'] += pl.bit(32)
        elif kind == 'sonarPing':
            wire = pl.u64(16)
            if ((wire & TAG_MASK) >> 53) != tag:
                continue
            stat['sonar'] += 1
            if wire not in opened:
                plain = unseal(key, wire, streams)
                opened[wire] = parse(plain) if plain is not None else None
            m = opened[wire]
            if m is None:
                stat['unreadable'] += 1
                continue
            if m['state'] & 1:
                stat['claims'] += 1
                stat['false_claims'] += q_us in bodies
                if first['claim'] is None:
                    first['claim'] = rnd
            if m['kind'] != 'ping':
                continue
            stat['pings'] += 1
            if first['ping'] is None:
                first['ping'] = rnd
            if m['dead']:
                stat['notices'] += 1
                continue
            revenge = rnd >= REVENGE_ROUND and q_us not in bodies and q_them in bodies
            hid = m['id']
            rec = hunters.setdefault(hid, {'first': rnd, 'early': not revenge, 'last': rnd, 'rounds': 0,
                                           'min_dist': None})
            if hid not in early_ids.get(rnd, ()) and hid not in rev_ids.get(rnd, ()):
                rec['rounds'] += 1
                stat['ping_age'] += rnd - m['when']
                stat['ping_count'] += 1
            rec['last'] = rnd
            (rev_ids if revenge else early_ids).setdefault(rnd, set()).add(hid)
            sample(hid)
            if (hid, rnd) not in hunt_turns and turn_start.get(hid, (None,))[0] == rnd:
                hunt_turns[(hid, rnd)] = {'her_cell': (m['cell'] % W, m['cell'] // W), 'start': turn_start[hid][1],
                                          'revenge': revenge}
    if rnd:
        close_round()

    # Portals: every hunter turn that starts beside one, and every hunter turn that goes through one.
    chances = [t for t in hunt_turns.values() if any(side(t['start'], ch) == 2 for ch in STEP)]
    walks, portal_log = {}, []
    for c in crossings:
        turn = hunt_turns.get((c['id'], c['round']))
        if turn is None:
            continue
        if turn['her_cell'] not in walks:
            walks[turn['her_cell']] = walk_from(turn['her_cell'])
        a, b = walks[turn['her_cell']].get(c['from']), walks[turn['her_cell']].get(c['to'])
        closer = b is not None and (a is None or b < a)
        portal_log.append({'round': c['round'], 'id': c['id'], 'from': c['from'], 'to': c['to'],
                           'her_cell': turn['her_cell'], 'walk_before': a, 'walk_after': b,
                           'revenge': turn['revenge'],
                           'kind': 'closer' if closer else 'boxed' if c['boxed'] else 'stray'})

    d_us, d_them = death.get(q_us), death.get(q_them)
    for hid, rec in hunters.items():
        dead = death.get(hid)
        rec['death'] = dead[0] if dead else None
        rec['death_reason'] = dead[1] if dead else None
        rec['killed_her'] = bool(dead and d_them and dead[0] == d_them[0] and dead[1] == 'head-on' and
                                 d_them[1] == 'head-on' and rec['last'] >= dead[0] - FIRE_WAIT)
        rec['died_hunting'] = bool(dead and dead[0] <= rec['last'] + FIRE_WAIT)
        rec['wasted'] = rec['died_hunting'] and not rec['killed_her'] and (rec['min_dist'] is None or rec['min_dist'] > 1)
    late = [r for r in opp_rounds if r > QUIET]
    first_opp = late[0] if late else None
    ping_rounds = set(early_ids) | set(rev_ids)
    fired = first_opp is not None and any(first_opp - 1 <= r <= first_opp + FIRE_WAIT for r in ping_rounds)
    early_hunters = [r for r in hunters.values() if r['early']]
    mine = [len(b) for i, b in bodies.items() if team_of.get(i) == ours]
    theirs = [len(b) for i, b in bodies.items() if team_of.get(i) != ours]
    in_window = bool(d_them and d_us and d_them[0] >= max(REVENGE_ROUND, d_us[0]))
    return {
        'digests': digests,
        'rounds': rnd,
        'win': int(winner == ours),
        'queen_death': d_us[0] if d_us else None,
        'foe_death': d_them[0] if d_them else None,
        'foe_death_reason': d_them[1] if d_them else None,
        'foe_killed_by_hunter': any(r['killed_her'] for r in hunters.values()),
        'foe_died_early': bool(d_them and not in_window),
        'foe_died_in_revenge': in_window,
        'first_ping': first['ping'],
        'first_opportunity': first_opp,
        'opportunity_rounds': len(opp_rounds),
        'sighting_rounds': len(sight_rounds),
        'sighting_after_quiet': any(r > QUIET for r in sight_rounds),
        'scout_fired': fired,
        'hunters': len(hunters),
        'early_hunters': len(early_hunters),
        'early_hunters_died_hunting': sum(1 for r in early_hunters if r['died_hunting']),
        'early_hunters_wasted': sum(1 for r in early_hunters if r['wasted']),
        'early_hunters_next_to_her': sum(1 for r in early_hunters if r['min_dist'] is not None and r['min_dist'] <= 1),
        'early_hunt_rounds': len(early_ids),
        'early_hunter_rounds': sum(len(v) for v in early_ids.values()),
        'early_hunter_rounds_before_300': sum(len(v) for r, v in early_ids.items() if r < 300),
        'dragon_rounds_before_300': stat['dragon_rounds'],
        'early_max_hunters': max((len(v) for v in early_ids.values()), default=0),
        'early_dist_samples': len(early_d),
        'early_dist_near': sum(1 for d in early_d if d <= NEAR),
        'early_dist_sum': sum(early_d),
        'revenge_window_rounds': stat['window'],
        'revenge_hunt_rounds': stat['window_hunt'],
        'revenge_hunter_rounds': sum(len(v) for v in rev_ids.values()),
        'revenge_ping_rounds': len(rev_ids),
        'revenge_hunters': len({i for v in rev_ids.values() for i in v}),
        'revenge_max_hunters': max((len(v) for v in rev_ids.values()), default=0),
        'revenge_dist_samples': len(rev_d),
        'revenge_dist_sum': sum(rev_d),
        'queen_dead_messages': stat['claims'],
        'queen_dead_messages_while_alive': stat['false_claims'],
        'first_queen_dead_message': first['claim'],
        'queen_pings': stat['pings'],
        'her_death_notices': stat['notices'],
        'ping_age_sum': stat['ping_age'],
        'ping_age_count': stat['ping_count'],
        'sonar_messages': stat['sonar'],
        'unreadable_own_sonar': stat['unreadable'],
        'cpu_points': stat['points'],
        'actions': stat['actions'],
        'cpu_points_max': stat['points_max'],
        'timeouts': stat['tle'],
        'marks': marks,
        'end_only_their_queen': q_us not in bodies and q_them in bodies,
        'end_only_our_queen': q_us in bodies and q_them not in bodies,
        'end_both_dead': q_us not in bodies and q_them not in bodies,
        'end_longest_us': max(mine, default=0),
        'end_longest_them': max(theirs, default=0),
        'end_total_us': sum(mine),
        'end_total_them': sum(theirs),
        'portal_sides': sum(1 for v in edges.values() if v == 2),
        'hunter_turns': len(hunt_turns),
        'portal_chances': len(chances),
        'portal_chances_revenge': sum(1 for t in chances if t['revenge']),
        'our_crossings': len(crossings),
        'hunter_crossings': len(portal_log),
        'hunter_crossings_closer': sum(1 for c in portal_log if c['kind'] == 'closer'),
        'hunter_crossings_boxed': sum(1 for c in portal_log if c['kind'] == 'boxed'),
        'hunter_crossings_stray': sum(1 for c in portal_log if c['kind'] == 'stray'),
        'hunter_rounds_walk_measured': stat['walk_rounds'],
        'hunter_rounds_walk_to_her': stat['walk_ok'],
        'portal_log': portal_log,
        'hunter_log': {str(i): r for i, r in sorted(hunters.items())},
    }


def job(args):
    return scan(*args)


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


def ratio(a, b):
    return round(a / b, 3) if b else None


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
    keys = sorted(base)
    jobs = [(src[k], 'A' if k[2] == '0' else 'B') for k in keys for src in (base, cand)]
    with cf.ProcessPoolExecutor(int(os.environ.get('WORKERS', '4'))) as pool:
        scans = list(pool.map(job, jobs))

    pairs = []
    for n, key in enumerate(keys):
        b, c = scans[2 * n], scans[2 * n + 1]
        diff = first_diff(b.pop('digests'), c.pop('digests'))
        pairs.append({
            'map': key[0], 'seed': key[1], 'side': key[2], 'first_diff_round': diff,
            'silent_ok': diff is None or (c['first_ping'] is not None and diff >= c['first_ping']),
            'opportunity': c['first_opportunity'] is not None,
            'false_alarm': c['queen_dead_messages_while_alive'] > 0,
            'revenge_game': c['revenge_window_rounds'] >= MIN_WINDOW,
            'triggered': c['revenge_window_rounds'] >= MIN_WINDOW and c['queen_dead_messages'] > 0,
            'base': b, 'candidate': c,
        })

    def total(rows, tag, field):
        return sum(int(p[tag][field] or 0) for p in rows)

    def both(fn):
        return {t: fn(t) for t in ('base', 'candidate')}

    def at_mark(mark, alive=False):
        """Pairs where both games reached the mark (and, with alive, our queen was alive there in both)."""
        return [p for p in pairs if all(mark in p[t]['marks'] and (not alive or p[t]['marks'][mark]['queen_alive'])
                                        for t in ('base', 'candidate'))]

    def mark_mean(tag, mark, field, rows):
        vals = [p[tag]['marks'][mark][field] for p in rows]
        return round(sum(vals) / len(vals), 2) if vals else None

    opp = [p for p in pairs if p['opportunity']]
    revenge = [p for p in pairs if p['revenge_game']]
    triggered = [p for p in revenge if p['triggered']]
    hunt_rounds = total(pairs, 'candidate', 'early_hunt_rounds')
    hunter_rounds = total(pairs, 'candidate', 'early_hunter_rounds')
    samples = total(pairs, 'candidate', 'early_dist_samples')
    near = total(pairs, 'candidate', 'early_dist_near')
    early_hunters = total(pairs, 'candidate', 'early_hunters')
    wasted = total(pairs, 'candidate', 'early_hunters_wasted')
    share = ratio(total(pairs, 'candidate', 'early_hunter_rounds_before_300'),
                  total(pairs, 'candidate', 'dragon_rounds_before_300'))
    econ = both(lambda t: mark_mean(t, 300, 'total_us', at_mark(300)))
    econ_alive = both(lambda t: mark_mean(t, 300, 'total_us', at_mark(300, True)))
    cpu = both(lambda t: ratio(total(pairs, t, 'cpu_points'), total(pairs, t, 'actions')))
    sonar = both(lambda t: total(pairs, t, 'sonar_messages'))
    tle = both(lambda t: total(pairs, t, 'timeouts'))
    fired = sum(1 for p in opp if p['candidate']['scout_fired'])
    rev_hunted = sum(1 for p in triggered if p['candidate']['revenge_ping_rounds'] > 0)
    mean_early = ratio(hunter_rounds, hunt_rounds)
    mean_revenge = ratio(total(revenge, 'candidate', 'revenge_hunter_rounds'),
                         total(revenge, 'candidate', 'revenge_ping_rounds'))
    # No recorded points means CPU was not measured; the traffic check then rests on sonar and timeouts.
    cpu_ratio = ratio(cpu['candidate'], cpu['base']) if cpu['base'] and cpu['candidate'] is not None else None
    sonar_ratio = ratio(sonar['candidate'], sonar['base'])
    chances = total(pairs, 'candidate', 'portal_chances')
    chance_games = sum(1 for p in pairs if p['candidate']['portal_chances'])
    crossed = {k: total(pairs, 'candidate', f'hunter_crossings{k}') for k in ('', '_closer', '_boxed', '_stray')}
    walk_rounds = total(pairs, 'candidate', 'hunter_rounds_walk_measured')
    walk_ok = total(pairs, 'candidate', 'hunter_rounds_walk_to_her')
    sightings = sum(1 for p in pairs if p['candidate']['sighting_after_quiet'])

    checks = {
        'silent': all(p['silent_ok'] for p in pairs),
        'target_seen': len(opp) >= MIN_GAMES,
        'scout_fires': fired >= FIRE_SHARE * len(opp) if opp else None,
        'one_early_hunter': mean_early <= ONE_MAX if hunt_rounds else None,
        'follows': 2 * near >= samples if samples else None,
        'not_wasted': 2 * wasted <= early_hunters if early_hunters else None,
        'small_cost': share <= HUNT_SHARE if hunt_rounds and share is not None else None,
        'no_false_alarm': not any(p['false_alarm'] for p in pairs),
        'revenge_seen': len(revenge) >= MIN_REVENGE,
        'revenge_trigger': len(triggered) >= TRIGGER_SHARE * len(revenge) if revenge else None,
        'revenge_hunt': 2 * rev_hunted > len(triggered) if triggered else None,
        'traffic': (sonar_ratio <= COST_RATIO and (cpu_ratio is None or cpu_ratio <= COST_RATIO) and
                    tle['candidate'] <= tle['base']) if sonar_ratio is not None else None,
        'portal_seen': chance_games >= PORTAL_GAMES and chances >= PORTAL_CHANCES,
        'portal_rule': crossed['_stray'] == 0 if chances else None,
    }
    passed = all(v is True for v in checks.values())
    failed = [k for k, v in checks.items() if v is False]
    unseen = [k for k, v in checks.items() if v is None]

    foe_deaths = both(lambda t: sum(1 for p in pairs if p[t]['foe_death'] is not None))
    facts = (
        f"{len(pairs)} pairs. Switch on: {sightings} games had a small dragon see her after round {QUIET}, "
        f"{len(opp)} of them with a walk to her that needs no portal; a queen ping followed within {FIRE_WAIT} "
        f"rounds of the first such chance in {fired}. Early hunting: {early_hunters} hunters over "
        f"{hunt_rounds} rounds, {mean_early} dragons pinging per hunt round (max "
        f"{max((p['candidate']['early_max_hunters'] for p in pairs), default=0)}), {share} of our dragon-rounds "
        f"before round 300; the hunter was within {NEAR} cells of her in {near} of {samples} hunter-rounds; "
        f"{total(pairs, 'candidate', 'early_hunters_next_to_her')} hunters got next to her, "
        f"{total(pairs, 'candidate', 'early_hunters_died_hunting')} died while hunting, {wasted} of those without "
        f"ever getting next to her. Revenge (our queen dead, theirs alive, round {REVENGE_ROUND}+, for "
        f"{MIN_WINDOW}+ rounds): {len(revenge)} games, 'our queen is dead' sent in {len(triggered)}, hunters "
        f"pinged her in {rev_hunted} of those ({mean_revenge} dragons per hunt round). 'Our queen is dead' while "
        f"she was alive: {sum(1 for p in pairs if p['false_alarm'])} games. Their queen died in "
        f"{foe_deaths['candidate']} games with the switch on vs {foe_deaths['base']} without "
        f"({total(pairs, 'candidate', 'foe_killed_by_hunter')} head-on by a hunter). Our total length at round 300: "
        f"{econ['candidate']} vs {econ['base']} ({len(at_mark(300))} pairs; with our queen alive in both "
        f"{econ_alive['candidate']} vs {econ_alive['base']}, {len(at_mark(300, True))} pairs). Our sonar messages "
        f"{sonar['candidate']} vs {sonar['base']}; timeouts {tle['candidate']} vs {tle['base']}; CPU points "
        f"{'not in the replay' if cpu_ratio is None else str(cpu['candidate']) + ' vs ' + str(cpu['base'])}. "
        f"Portals: {chances} hunter turns started beside a portal ({chance_games} games); hunters went through "
        f"one {crossed['']} times: {crossed['_closer']} onto a tile with a shorter walk to the pinged cell, "
        f"{crossed['_boxed']} with no free step left, {crossed['_stray']} neither (the rule allows none). A hunter "
        f"had a walk to her without any portal in {walk_ok} of {walk_rounds} hunter-rounds. Wins "
        f"{total(pairs, 'candidate', 'win')} vs {total(pairs, 'base', 'win')} (not a result: too few games).")
    if passed:
        note = 'Shown. ' + facts
    elif failed:
        note = (f"Not shown, failed: {', '.join(failed)}" + (f"; never seen: {', '.join(unseen)}" if unseen else '') +
                '. ' + facts)
    else:
        note = f"Not shown: target never seen for {', '.join(unseen)}. " + facts

    out = {
        'passed': bool(passed), 'note': note, 'checks': checks, 'built_as': BUILT_AS,
        'pairs': len(pairs),
        'identical_pairs': sum(1 for p in pairs if p['first_diff_round'] is None),
        'silent_ok_pairs': sum(1 for p in pairs if p['silent_ok']),
        'opportunity_games': len(opp),
        'scout_fired_games': fired,
        'early_hunters': early_hunters,
        'early_hunt_rounds': hunt_rounds,
        'early_hunter_rounds': hunter_rounds,
        'mean_early_hunters_per_hunt_round': mean_early,
        'early_hunt_share_before_300': share,
        'early_hunter_rounds_measured': samples,
        'early_hunter_rounds_near': near,
        'mean_early_hunter_distance': ratio(total(pairs, 'candidate', 'early_dist_sum'), samples),
        'early_hunters_next_to_her': total(pairs, 'candidate', 'early_hunters_next_to_her'),
        'early_hunters_died_hunting': total(pairs, 'candidate', 'early_hunters_died_hunting'),
        'early_hunters_wasted': wasted,
        'mean_ping_age': ratio(total(pairs, 'candidate', 'ping_age_sum'), total(pairs, 'candidate', 'ping_age_count')),
        'revenge_games': both(lambda t: sum(1 for p in pairs if p[t]['revenge_window_rounds'] >= MIN_WINDOW)),
        'revenge_triggered_games': len(triggered),
        'revenge_hunted_games': rev_hunted,
        'revenge_window_rounds': total(revenge, 'candidate', 'revenge_window_rounds'),
        'revenge_hunt_rounds': total(revenge, 'candidate', 'revenge_hunt_rounds'),
        'mean_revenge_hunters_per_hunt_round': mean_revenge,
        'mean_revenge_hunter_distance': ratio(total(pairs, 'candidate', 'revenge_dist_sum'),
                                              total(pairs, 'candidate', 'revenge_dist_samples')),
        'false_alarm_games': sum(1 for p in pairs if p['false_alarm']),
        'queen_dead_messages': both(lambda t: total(pairs, t, 'queen_dead_messages')),
        'queen_pings': both(lambda t: total(pairs, t, 'queen_pings')),
        'her_death_notices': total(pairs, 'candidate', 'her_death_notices'),
        'our_queen_died_games': both(lambda t: sum(1 for p in pairs if p[t]['queen_death'] is not None)),
        'foe_queen_died_games': foe_deaths,
        'foe_queen_died_early': both(lambda t: total(pairs, t, 'foe_died_early')),
        'foe_queen_died_in_revenge': both(lambda t: total(pairs, t, 'foe_died_in_revenge')),
        'foe_queen_killed_by_hunter': total(pairs, 'candidate', 'foe_killed_by_hunter'),
        'foe_queen_death_reasons': both(lambda t: {r: sum(1 for p in pairs if p[t]['foe_death_reason'] == r)
                                                    for r in REASONS}),
        'end_only_their_queen': both(lambda t: total(pairs, t, 'end_only_their_queen')),
        'end_only_our_queen': both(lambda t: total(pairs, t, 'end_only_our_queen')),
        'end_both_dead': both(lambda t: total(pairs, t, 'end_both_dead')),
        'wins': both(lambda t: total(pairs, t, 'win')),
        'length_at_marks': {str(m): both(lambda t, m=m: {
            f: mark_mean(t, m, f, at_mark(m)) for f in ('total_us', 'units_us', 'longest_us', 'total_them',
                                                        'longest_them')}) for m in MARKS},
        'pairs_at_marks': {str(m): len(at_mark(m)) for m in MARKS},
        'total_length_at_300_queen_alive': econ_alive,
        'pairs_at_300_queen_alive': len(at_mark(300, True)),
        'cpu_points_per_action': cpu,
        'cpu_ratio': cpu_ratio,
        'timeouts': tle,
        'sonar_messages': sonar,
        'sonar_ratio': sonar_ratio,
        'unreadable_own_sonar': both(lambda t: total(pairs, t, 'unreadable_own_sonar')),
        'hunter_turns': total(pairs, 'candidate', 'hunter_turns'),
        'portal_chances': chances,
        'portal_chances_revenge': total(pairs, 'candidate', 'portal_chances_revenge'),
        'portal_chance_games': chance_games,
        'hunter_crossings': crossed[''],
        'hunter_crossings_closer': crossed['_closer'],
        'hunter_crossings_boxed': crossed['_boxed'],
        'hunter_crossings_stray': crossed['_stray'],
        'our_crossings': both(lambda t: total(pairs, t, 'our_crossings')),
        'hunter_rounds_walk_measured': walk_rounds,
        'hunter_rounds_walk_to_her': walk_ok,
        'sighting_games': sightings,
        'by_map': {m: {'portal_sides': max(p['candidate']['portal_sides'] for p in rows),
                       'sighting_games': sum(1 for p in rows if p['candidate']['sighting_after_quiet']),
                       'opportunity_games': sum(1 for p in rows if p['opportunity']),
                       'scout_fired_games': sum(1 for p in rows if p['opportunity'] and p['candidate']['scout_fired']),
                       'hunter_turns': total(rows, 'candidate', 'hunter_turns'),
                       'portal_chances': total(rows, 'candidate', 'portal_chances'),
                       'hunter_crossings': total(rows, 'candidate', 'hunter_crossings'),
                       'hunter_crossings_closer': total(rows, 'candidate', 'hunter_crossings_closer'),
                       'hunter_crossings_boxed': total(rows, 'candidate', 'hunter_crossings_boxed'),
                       'hunter_crossings_stray': total(rows, 'candidate', 'hunter_crossings_stray'),
                       'hunter_rounds_walk_measured': total(rows, 'candidate', 'hunter_rounds_walk_measured'),
                       'hunter_rounds_walk_to_her': total(rows, 'candidate', 'hunter_rounds_walk_to_her'),
                       'early_hunters': total(rows, 'candidate', 'early_hunters'),
                       'revenge_games': sum(1 for p in rows if p['revenge_game']),
                       'foe_queen_died_games': both(lambda t, rows=rows: sum(1 for p in rows
                                                                              if p[t]['foe_death'] is not None))}
                   for m in sorted({p['map'] for p in pairs}) for rows in [[p for p in pairs if p['map'] == m]]},
        'settings': {'max_len': MAX_LEN, 'revenge_round': REVENGE_ROUND, 'quiet': QUIET, 'min_games': MIN_GAMES,
                     'fire_share': round(FIRE_SHARE, 3), 'fire_wait': FIRE_WAIT, 'one_max': ONE_MAX, 'near': NEAR,
                     'hunt_share': HUNT_SHARE, 'min_revenge': MIN_REVENGE, 'min_window': MIN_WINDOW,
                     'trigger_share': round(TRIGGER_SHARE, 3), 'cost_ratio': COST_RATIO,
                     'portal_games': PORTAL_GAMES, 'portal_chances': PORTAL_CHANCES},
        'limits': 'Who hunts is read from our own sonar (a hunter pings every turn); hunt state inside the bot is '
                  'not in the replay. Early/revenge is replay truth, not what each dragon believed. A sighting or '
                  'opportunity uses end-of-round positions and the real map, and ignores the bot\'s own leader test '
                  'and what the dragon had seen of the walls, so some are not real chances. Distances are grid distances with wrap, walls and portals ignored; only the '
                  'portal numbers use walks on the real map. The portal rule is judged against the real map and the '
                  'cell in the hunter\'s own ping, so it does not show what the dragon had seen: a crossing can be '
                  'closer on the real map without the dragon having been sure, and a hunter that never takes a '
                  'useful portal is not caught by it. "Boxed" looks at dragon bodies when the hunter moved. There is '
                  'no switch-off counterpart for the portal numbers (the base bot has no hunters). A kill by a '
                  'hunter means a hunter and her both died head-on in the same round. The two games of a pair '
                  'diverge after the first hunt, so later rounds are not round-for-round comparable. Kept replays '
                  'carry no CPU points, so CPU is judged by timeouts only.',
        'games': pairs,
    }
    with open(a.output, 'w') as f:
        json.dump(out, f, indent=1)
    print(note)


if __name__ == '__main__':
    main()
