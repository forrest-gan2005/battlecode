#!/usr/bin/env python3
"""Card #50 revenge-hunt mechanism check (QH_REVENGE_LONG): once our queen is dead (from round 100) a small dragon
keeps hunting their queen on a sighting up to 60 rounds old instead of 20.

usage: python3 work/card_50_check.py --replays DIR --base base --candidate candidate --output FILE
Reads paired replays DIR/<tag>_<map>_<seed>_<side>.replay (side 0 = we are team A).

Words:
  queen          the dragon with id 0 or 1, one per team. At round 500 the longer queen wins, a dead queen counts 0.
  sighting       the cell and round where one of our dragons last saw their queen's head. Hunters pass it on by sonar.
  hunter turn    a turn in which one of our dragons sends a queen ping (its id, her cell, the round she was seen),
                 read with our codec key. A dragon pings on every turn it hunts, so "who pings" is "who hunts".
  age            the round of the hunter turn minus the round in the ping. The release drops a sighting at age 21.
  revenge turn   a hunter turn at round 100 or later whose ping says the sender believes our queen is dead. This is
                 the bot's own belief, carried in two bits of the ping; the switch looks at nothing else.
  long turn      a revenge turn with age above 20. Only the switch can make one.
  hunt           one dragon's hunter turns in a row. One turn without a ping in between still counts: a dragon whose
                 tail tip is on a portal opening sends the tail warning (#42) instead of the queen ping that turn.
  long hunt      a hunt with at least one long turn; its "long part" starts at the first long turn.
  finds her      on a turn of the long part the hunter starts with her head inside its 7x7 view. From then on it
                 hunts on its own fresh sighting like any hunter today.
  path steps     shortest way over open tile sides and through portals; kelp blocks, dragon bodies are ignored.
  walk           the same without portals (the bot's own measure for "can I get to her cell"). Used to say whether
                 a long turn ends closer to her last cell; with no walk the hunter is in a part of the map that
                 only a portal connects to it.
  lone turn      a turn of their queen at round 100 or later while our queen is dead (replay truth).
  revenge window the lone turns that come after one of ours has said "our queen is dead" by sonar. Until then
                 nobody on our side knows and the switch has nothing to act on. A pair "has a revenge window" when
                 its switch-off game has at least MIN_WINDOW such turns.
  stale chance   a switch-off hunt that ends because the sighting turned 21 rounds old: its last ping is a revenge
                 turn of age exactly 20, the dragon is alive, still 4 or shorter and not next to her last cell, and
                 their queen is alive. Counted to show how often the 20 rounds are what stops a revenge hunt today.
  near           one of our heads within NEAR path steps of her head at the start of a lone turn.
  next to her    within 1 path step.

Expectation, written before any switch-on game was run. The thresholds are the constants below. The only games
looked at first were the 20 switch-off games of this build's identity run (old 10 maps, base against base, each
read from both sides): a revenge window came up on 2 of those 40 sides and a stale chance on 1, so the target is
rare and may not show in 16 pairs.
  1. silent: a pair plays the same game until the switch can act: no difference before round 100, and none before
     the first sign that one of ours holds "our queen is dead" (her real death, or a sonar message saying so).
  2. target seen: at least MIN_TARGET_GAMES pairs have a revenge window.
  3. fires: in at least FIRE_SHARE of those pairs the switch-on game has a long turn, the switch-on games hold at
     least MIN_LONG_TURNS long turns in all, and the switch-off games hold none.
  4. as specified: every long turn is at round 100 or later, has age 21 to 60, and its sender is not a queen and
     is 4 or shorter when the turn starts.
  5. arrives: at least MIN_LONG_HUNTS long hunts ran their course (did not stop because the game ended or she died
     before the hunter found her), and at least ARRIVE_SHARE of them find her.
passed = all five. A check whose target never appeared is null and never counts as a pass.
fires_as_specified = 1, 3 and 4 (the switch does what the card says); target_seen = 2; arrives = 5.

Reported next to that, not gated (16 pairs cannot settle them). The card's expected signals: our heads within 12
path steps of her per lone turn (the card asks for 2 or more; 1.15 on the ladder, which may have counted steps a
little differently, so base against candidate here is the comparison that counts), her head-on deaths against one
of ours, and their lone queen alive at the end. The card's two "this is wrong" signs: our heads are already next
to her in the switch-off games and she lives; our pearls after round 300 fall by more than a tenth. The card's
premise: stale chances, and how switch-off revenge hunts end otherwise. From the questions step: how long hunts
end (found her / reached her last cell and she was gone, with how far she was by then / sighting 60 rounds old /
died / other), hunter turns after round 300, and our longest at the end.
Exit code 0 for a completed measurement, nonzero for missing or unpaired replays.
"""
import argparse, concurrent.futures as cf, glob, hashlib, json, os, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

FRESH = 20
LONG = 60
MAX_LEN = 4
REVENGE_ROUND = 100
VIEW = 3
NEAR = 12
LATE = 300
LAST_ROUND = 499
MIN_WINDOW = 20
MIN_TARGET_GAMES = 2
FIRE_SHARE = 0.5
MIN_LONG_TURNS = 20
MIN_LONG_HUNTS = 5
ARRIVE_SHARE = 1 / 3
PEARL_DROP = 0.1
LOG_MAX = 60
DIRS = 'NESW'
STEP = {'N': (0, -1), 'E': (1, 0), 'S': (0, 1), 'W': (-1, 0)}
REASONS = ['wall', 'self', 'body', 'head-on', 'no action']
ENDS = ['found her', 'reached her last cell, she was gone', 'sighting 60 rounds old', 'sighting 20 rounds old',
        'died', 'she died', 'grew past 4', 'game over', 'other']
BUILT_AS = (
    "How the card was built. One switch, QH_REVENGE_LONG. With it on, a dragon that believes our queen is dead, "
    "from round 100, keeps a sighting of their queen usable for 60 rounds (QH_REVENGE_FRESH) instead of 20. "
    "Everything else is the release hunt: only dragons of length 4 or less that are not our queen and not the "
    "leader hunt, a hunter that gets next to her last cell without seeing her drops that sighting and waits for "
    "a newer one, sightings are passed on only by dragons that are hunting, and the notice that their queen died "
    "keeps its 20 rounds. Defaults taken at the questions step: the 60 rounds apply only while the revenge "
    "condition holds (before round 100, or with our queen alive, it stays 20); each dragon goes by its own belief "
    "every round, so one that sees our queen alive again is back to 20 at once; no search around an old cell; no "
    "map names and no per-map values.")

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


def unseal(key, wire, streams):
    """Plain message, or None when the keyed check fails."""
    check = (wire & CHECK_MASK) >> 55
    if check not in streams:
        streams[check] = prf(key, CHECK_MASK | check) & CIPHER_MASK
    plain = (wire & (M64 & ~CHECK_MASK)) ^ streams[check]
    return plain if (prf(key, plain & (M64 & ~CHECK_MASK)) & 0xFF) == check else None


def parse(plain):
    """Leader message (two bits carry the "our queen is dead" state) or queen ping; else 'other'."""
    body = plain & ((1 << 55) - 1)
    if plain >> 63 == 0:
        return {'kind': 'leader', 'state': (body >> 26) & 0x3}
    if (body >> 42) & 0x7FF == PING_KIND:
        return {'kind': 'ping', 'cell': body & 0x3FFF, 'when': (body >> 14) & 0x1FF, 'dead': (body >> 23) & 1,
                'state': (body >> 24) & 0x3, 'id': (body >> 26) & 0xFFFF}
    return {'kind': 'other', 'state': 0}


def read_map(text):
    """Size, starting bodies and tile sides. Side kinds: 0 open, 1 kelp, 2 portal (its last field names the pair)."""
    lines = [line.split() for line in text.splitlines() if line.strip()]
    W, H = map(int, next(q for q in lines if q[0] == 'MAP')[1:3])
    bodies, team_of, kinds, partner, pairs = {}, {}, {}, {}, {}

    def canon(i):
        """(upright, x, y) for an edge id; a border side may be listed twice, padding slots are dropped."""
        row, x = divmod(i, W + 1)
        y, upright = divmod(row, 2)
        if upright:
            return None if y >= H else (1, x % W, y)
        return None if x >= W else (0, x, y % H)

    for q in lines:
        if q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
        elif q[0] == 'EDGE':
            key = canon(int(q[1]))
            if key is None:
                continue
            kinds[key] = max(kinds.get(key, 0), int(q[2]))
            if int(q[2]) == 2 and len(q) > 3 and int(q[3]) >= 0:
                pairs.setdefault(int(q[3]), set()).add(key)
    for ends in pairs.values():
        if len(ends) == 2:
            a, b = sorted(ends)
            partner[a], partner[b] = b, a
    return W, H, bodies, team_of, kinds, partner


class Board:
    def __init__(self, W, H, kinds, partner):
        self.W, self.H, self.kinds, self.partner = W, H, kinds, partner
        self.ways = {}

    def edge(self, cell, ch):
        x, y = cell
        if ch == 'N':
            return (0, x, y)
        if ch == 'S':
            return (0, x, (y + 1) % self.H)
        if ch == 'W':
            return (1, x, y)
        return (1, (x + 1) % self.W, y)

    def side(self, cell, ch):
        return self.kinds.get(self.edge(cell, ch), 0)

    def beside(self, cell, ch):
        return (cell[0] + STEP[ch][0]) % self.W, (cell[1] + STEP[ch][1]) % self.H

    def through(self, cell, ch):
        """Tile reached by leaving `cell` on side ch (through the portal when it is one); None when shut."""
        e = self.edge(cell, ch)
        kind = self.kinds.get(e, 0)
        if kind == 1:
            return None
        if kind != 2:
            return self.beside(cell, ch)
        p = self.partner.get(e)
        if p is None or p[0] != e[0]:
            return None
        _, x, y = p
        if ch == 'N':
            return x, (y - 1) % self.H
        if ch == 'W':
            return (x - 1) % self.W, y
        return x, y

    def steps(self, cell):
        """(tiles one path step away, tiles one walk step away)."""
        if cell not in self.ways:
            path = [self.through(cell, ch) for ch in DIRS]
            walk = [self.beside(cell, ch) for ch in DIRS if self.side(cell, ch) == 0]
            self.ways[cell] = ([c for c in path if c is not None], walk)
        return self.ways[cell]

    def spread(self, source, portals=True, limit=None):
        """Steps from `source` to every tile within `limit`."""
        dist, queue = {source: 0}, deque([source])
        while queue:
            c = queue.popleft()
            if limit is not None and dist[c] >= limit:
                continue
            for n in self.steps(c)[0 if portals else 1]:
                if n not in dist:
                    dist[n] = dist[c] + 1
                    queue.append(n)
        return dist


def scan(path, ours):
    """One pass over a replay for our side."""
    root = replay.load(path).root()
    W, H, bodies, team_of, kinds, partner = read_map(root.text(0))
    board = Board(W, H, kinds, partner)
    result = root.pointer(4)
    winner = ('A', 'B')[result.u16(6)] if result.u16(4) == 1 else None
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

    stat = {k: 0 for k in (
        'sonar', 'unreadable', 'hunter_turns', 'revenge_turns', 'long_turns', 'off_spec', 'hunter_turns_late',
        'hunter_turns_lone', 'notices', 'lone_turns', 'lone_turns_known', 'near_sum', 'near_small_sum',
        'near_hunting_sum', 'lone_turns_near2', 'lone_turns_next', 'her_len_sum', 'pearls', 'pearls_late', 'turns',
        'turns_late', 'points', 'points_max', 'tle', 'deaths', 'deaths_late', 'long_closer', 'long_same',
        'long_farther', 'long_no_walk', 'bad_steps')}
    digests, h = {}, hashlib.sha1()
    death, hunts, done, off_log = {}, {}, [], []
    walks, reach = {}, {}
    first = {'claim': None, 'ping': None, 'long': None}
    her_death = None
    rnd = turn_no = 0
    cur = None

    def her_reach():
        """Path steps from her head to every tile, for where she stands now."""
        her = bodies[q_them][0]
        if reach.get('at') != her:
            reach['at'], reach['dist'] = her, board.spread(her)
        return reach['dist']

    def walk_to(cell):
        if cell not in walks:
            walks[cell] = board.spread(cell, portals=False)
        return walks[cell]

    def finish(hunt, why=None):
        """Close a hunt and say how it ended."""
        did = hunt['id']
        dead = death.get(did)
        her = death.get(q_them)
        if hunt['found']:
            end = 'found her'
        elif why == 'game over':
            end = 'game over'
        elif dead is not None:
            end = 'died'
        elif her is not None and her[0] <= hunt['last'] + 1:
            end = 'she died'
        elif hunt['quiet_at'] is not None and sum(gap(hunt['quiet_at'], hunt['cell'])) <= 1:
            end = 'reached her last cell, she was gone'
        elif hunt['quiet_len'] is not None and hunt['quiet_len'] > MAX_LEN:
            end = 'grew past 4'
        elif hunt['age'] == LONG:
            end = 'sighting 60 rounds old'
        elif hunt['age'] == FRESH:
            end = 'sighting 20 rounds old'
        else:
            end = 'other'
        hunt['end'] = end
        # How far she was when the hunter stood at her last cell.
        hunt['her_steps_at_end'] = hunt['quiet_her'] if end == 'reached her last cell, she was gone' else None
        hunt['stale_chance'] = bool(end == 'sighting 20 rounds old' and hunt['revenge'])
        for k in ('quiet', 'quiet_at', 'quiet_len', 'quiet_her'):
            hunt.pop(k)
        done.append(hunt)

    def close_turn():
        nonlocal cur
        if cur is None:
            return
        t, cur = cur, None
        did = t['id']
        hunt = hunts.get(did)
        alive = did in bodies
        m = t['ping']
        if m is None:
            if hunt is not None:
                hunt['quiet'] += 1
                if hunt['quiet'] == 1:
                    hunt['quiet_at'], hunt['quiet_len'] = t['start'], t['len']
                    hunt['quiet_her'] = her_reach().get(t['start']) if q_them in bodies else None
                if hunt['quiet'] >= 2 or not alive:
                    finish(hunts.pop(did))
            return
        age = rnd - m['when']
        cell = (m['cell'] % W, m['cell'] // W)
        revenge = bool(m['state'] & 1) and rnd >= REVENGE_ROUND
        long = age > FRESH
        lone = rnd >= REVENGE_ROUND and q_us not in bodies
        stat['hunter_turns'] += 1
        stat['revenge_turns'] += revenge
        stat['long_turns'] += long
        stat['hunter_turns_late'] += rnd > LATE
        stat['hunter_turns_lone'] += lone
        if first['ping'] is None:
            first['ping'] = rnd
        if long:
            if first['long'] is None:
                first['long'] = rnd
            wrong = [w for w, bad in (('before round 100', rnd < REVENGE_ROUND), ('age above 60', age > LONG),
                                      ('sender is a queen', did <= 1), ('sender longer than 4', t['len'] > MAX_LEN),
                                      ('no "our queen is dead" in the ping', not m['state'] & 1)) if bad]
            if wrong:
                stat['off_spec'] += 1
                if len(off_log) < LOG_MAX:
                    off_log.append({'round': rnd, 'id': did, 'age': age, 'length': t['len'], 'why': wrong})
        if hunt is None:
            hunt = hunts[did] = {'id': did, 'first': rnd, 'last': rnd, 'turns': 0, 'long_turns': 0, 'first_long': None,
                                 'age': age, 'max_age': age, 'cell': cell, 'found': False, 'found_round': None,
                                 'steps_at_first_long': None, 'min_steps': None, 'next_to_her': False,
                                 'quiet': 0, 'quiet_at': None, 'quiet_len': None, 'quiet_her': None}
        # 'revenge' is how the hunt stood on its last ping.
        hunt.update(last=rnd, age=age, cell=cell, revenge=revenge, quiet=0, quiet_at=None, quiet_len=None,
                    quiet_her=None)
        hunt['turns'] += 1
        hunt['long_turns'] += long
        hunt['max_age'] = max(hunt['max_age'], age)
        her_alive = q_them in bodies
        if long and hunt['first_long'] is None:
            hunt['first_long'] = rnd
            # She has not moved since this turn began.
            if her_alive:
                hunt['steps_at_first_long'] = her_reach().get(t['start'])
        elif hunt['first_long'] is not None and t['sees'] and not hunt['found']:
            hunt['found'], hunt['found_round'] = True, rnd
        if hunt['first_long'] is not None and alive and her_alive:
            steps = her_reach().get(bodies[did][0])
            if steps is not None:
                hunt['min_steps'] = steps if hunt['min_steps'] is None else min(hunt['min_steps'], steps)
                hunt['next_to_her'] = hunt['next_to_her'] or steps <= 1
        if long:
            walk = walk_to(cell)
            a, b = walk.get(t['start']), walk.get(bodies[did][0]) if alive else None
            if a is None or b is None:
                stat['long_no_walk'] += 1
            else:
                stat['long_closer' if b < a else 'long_farther' if b > a else 'long_same'] += 1
        if not alive:
            finish(hunts.pop(did))

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else '?'
        pl = ev.pointer(0)
        if kind == 'roundStart':
            close_turn()
            digests[rnd] = h.hexdigest()
            rnd = pl.i32(0)
            h = hashlib.sha1()
        elif kind == 'turnStart':
            close_turn()
        elif kind == 'dragonAction':
            close_turn()
            did = pl.i32(0)
            turn_no += 1
            if did not in bodies:
                continue
            her_alive = q_them in bodies
            if did == q_them and rnd >= REVENGE_ROUND and q_us not in bodies:
                near = board.spread(bodies[did][0], limit=NEAR)
                mine = [(i, near[b[0]]) for i, b in bodies.items() if team_of.get(i) == ours and b[0] in near]
                stat['lone_turns'] += 1
                stat['lone_turns_known'] += first['claim'] is not None
                stat['near_sum'] += len(mine)
                stat['near_small_sum'] += sum(1 for i, _ in mine if len(bodies[i]) <= MAX_LEN)
                stat['near_hunting_sum'] += sum(1 for i, _ in mine if i in hunts)
                stat['lone_turns_near2'] += len(mine) >= 2
                stat['lone_turns_next'] += any(d <= 1 for _, d in mine)
                stat['her_len_sum'] += len(bodies[did])
            if team_of.get(did) != ours:
                continue
            usage = pl.pointer(1)
            points = usage.u64(0) if usage else 0
            stat['turns'] += 1
            stat['turns_late'] += rnd > LATE
            stat['points'] += points
            stat['points_max'] = max(stat['points_max'], points)
            stat['tle'] += pl.bit(32)
            head = bodies[did][0]
            cur = {'id': did, 'start': head, 'len': len(bodies[did]), 'ping': None,
                   'sees': her_alive and max(gap(head, bodies[q_them][0])) <= VIEW}
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            head, tail = replay.point(pl.pointer(0)), replay.point(pl.pointer(1))
            h.update(f'u{did}{head}{tail}'.encode())
            body = bodies.setdefault(did, deque())
            before = len(body)
            if body and body[0] != head and head not in board.steps(body[0])[0]:
                stat['bad_steps'] += 1
            if not body or body[0] != head:
                body.appendleft(head)
            while len(body) > 1 and body[-1] != tail:
                body.pop()
            if team_of.get(did) == ours and before and len(body) > before:
                stat['pearls'] += len(body) - before
                stat['pearls_late'] += (len(body) - before) * (rnd > LATE)
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
            why = REASONS[reason] if reason < len(REASONS) else '?'
            death[did] = (rnd, why, turn_no)
            if team_of.get(did) == ours:
                stat['deaths'] += 1
                stat['deaths_late'] += rnd > LATE
            if did == q_them:
                her_death = {'round': rnd, 'reason': why, 'length': len(bodies.get(did, ())), 'turn': turn_no,
                             'lone': rnd >= REVENGE_ROUND and q_us not in bodies}
            bodies.pop(did, None)
            # A hunter killed on another dragon's turn.
            if did in hunts and (cur is None or cur['id'] != did):
                finish(hunts.pop(did))
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
            if m['state'] & 1 and first['claim'] is None:
                first['claim'] = rnd
            if m['kind'] != 'ping':
                continue
            if m['dead']:
                stat['notices'] += 1
            elif cur is not None and pl.i32(0) == cur['id'] and cur['ping'] is None:
                cur['ping'] = m
    close_turn()
    digests[rnd] = h.hexdigest()
    for did in sorted(hunts):
        finish(hunts.pop(did), 'game over')
    if stat['bad_steps']:
        raise ValueError(f"{path}: {stat['bad_steps']} head steps fit no open side or portal; map sides misread")

    # Her head-on death against one of ours: both heads die on the same turn.
    if her_death is not None:
        hit = [i for i, d in death.items() if i != q_them and d[2] == her_death['turn'] and d[1] == 'head-on' and
               team_of.get(i) == ours]
        her_death['by_ours_head_on'] = bool(her_death['reason'] == 'head-on' and hit)
        her_death['killer'] = hit[0] if her_death['by_ours_head_on'] else None
        last = [x for x in done if x['id'] == her_death['killer'] and x['last'] >= her_death['round'] - 2]
        her_death['killer_was_hunting'] = bool(last)
        her_death['killer_on_long_hunt'] = any(x['long_turns'] for x in last)
        del her_death['turn']
    mine = [len(b) for i, b in bodies.items() if team_of.get(i) == ours]
    theirs = [len(b) for i, b in bodies.items() if team_of.get(i) != ours]
    d_us = death.get(q_us)
    signs = [r for r in (d_us[0] if d_us else None, first['claim']) if r is not None]
    long_hunts = [x for x in done if x['long_turns']]
    return {
        'digests': digests,
        'rounds': rnd,
        'cells': W * H,
        'win': int(winner == ours),
        'queen_death': d_us[0] if d_us else None,
        'first_queen_dead_message': first['claim'],
        'first_sign_queen_dead': min(signs) if signs else None,
        'first_ping': first['ping'],
        'first_long_turn': first['long'],
        'her_death': her_death,
        'end_only_their_queen': q_us not in bodies and q_them in bodies,
        'end_only_our_queen': q_us in bodies and q_them not in bodies,
        'end_longest_us': max(mine, default=0),
        'end_longest_them': max(theirs, default=0),
        'end_total_us': sum(mine),
        'end_total_them': sum(theirs),
        'hunts': len(done),
        'stale_chances': sum(1 for x in done if x['stale_chance']),
        'long_hunts': len(long_hunts),
        'hunt_ends': {e: sum(1 for x in done if x['end'] == e) for e in ENDS},
        'revenge_hunt_ends': {e: sum(1 for x in done if x['end'] == e and x['revenge']) for e in ENDS},
        'long_hunt_ends': {e: sum(1 for x in long_hunts if x['end'] == e) for e in ENDS},
        **stat,
        'off_spec_log': off_log,
        'long_hunt_log': long_hunts,
        'stale_log': [x for x in done if x['stale_chance']][:LOG_MAX],
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


def ratio(a, b, digits=3):
    return round(a / b, digits) if b else None


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
    for n, k in enumerate(keys):
        b, c = scans[2 * n], scans[2 * n + 1]
        diff = first_diff(b.pop('digests'), c.pop('digests'))
        sign = c['first_sign_queen_dead']
        pairs.append({'map': k[0], 'seed': k[1], 'side': k[2], 'first_diff_round': diff,
                      'silent_ok': diff is None or (sign is not None and diff >= max(REVENGE_ROUND, sign)),
                      'base': b, 'candidate': c})

    def total(tag, field):
        return sum(int(p[tag][field] or 0) for p in pairs)

    def both(field):
        return {t: total(t, field) for t in ('base', 'candidate')}

    def ends(tag, field):
        return {e: sum(p[tag][field][e] for p in pairs) for e in ENDS if any(p[tag][field][e] for p in pairs)}

    games = len(pairs)
    silent = sum(1 for p in pairs if p['silent_ok'])
    changed = sum(1 for p in pairs if p['first_diff_round'] is not None)
    target = [p for p in pairs if p['base']['lone_turns_known'] >= MIN_WINDOW]
    fired = [p for p in target if p['candidate']['long_turns'] > 0]
    fire_share = ratio(len(fired), len(target))
    long_turns = both('long_turns')
    off_spec = both('off_spec')
    hunts = [x for p in pairs for x in p['candidate']['long_hunt_log']]
    judged = [x for x in hunts if x['end'] not in ('game over', 'she died')]
    found = [x for x in judged if x['end'] == 'found her']
    arrive_share = ratio(len(found), len(judged))
    target_seen = len(target) >= MIN_TARGET_GAMES
    checks = {
        'silent': silent == games,
        'target_seen': target_seen,
        'fires': (fire_share >= FIRE_SHARE and long_turns['candidate'] >= MIN_LONG_TURNS and long_turns['base'] == 0
                  if target_seen else None),
        'as_specified': off_spec['candidate'] == 0 if long_turns['candidate'] else None,
        'arrives': arrive_share >= ARRIVE_SHARE if len(judged) >= MIN_LONG_HUNTS else None,
    }
    passed = all(v is True for v in checks.values())
    fires_as_specified = all(checks[k] is True for k in ('silent', 'fires', 'as_specified'))

    lone = both('lone_turns')
    lone_games = {t: [p for p in pairs if p[t]['lone_turns'] > 0] for t in ('base', 'candidate')}
    near = {t: ratio(total(t, 'near_sum'), lone[t], 2) for t in lone}
    near_small = {t: ratio(total(t, 'near_small_sum'), lone[t], 2) for t in lone}
    near2 = {t: ratio(total(t, 'lone_turns_near2'), lone[t]) for t in lone}
    beside = {t: ratio(total(t, 'lone_turns_next'), lone[t]) for t in lone}
    her_len = {t: ratio(total(t, 'her_len_sum'), lone[t], 1) for t in lone}
    full = {t: [p for p in lone_games[t] if p[t]['rounds'] >= LAST_ROUND] for t in lone}
    alive_end = {t: sum(1 for p in full[t] if p[t]['end_only_their_queen']) for t in lone}
    alive_share = {t: ratio(alive_end[t], len(full[t])) for t in lone}

    def her_deaths(tag, field=None):
        rows = [p[tag]['her_death'] for p in pairs if p[tag]['her_death'] and p[tag]['her_death']['lone']]
        return sum(1 for d in rows if field is None or d[field])

    killed = {t: her_deaths(t) for t in lone}
    head_on = {t: her_deaths(t, 'by_ours_head_on') for t in lone}
    by_long = her_deaths('candidate', 'killer_on_long_hunt')
    # The card's first "this is wrong" sign, read from the switch-off games.
    lived_beside = sum(1 for p in lone_games['base']
                       if p['base']['lone_turns_next'] and p['base']['end_only_their_queen'])
    pearls = both('pearls_late')
    pearl_change = ratio(pearls['candidate'] - pearls['base'], pearls['base'])
    pearl_sign = None if pearl_change is None else pearl_change < -PEARL_DROP
    gone = [x for x in hunts if x['end'] == 'reached her last cell, she was gone']
    gone_steps = sorted(x['her_steps_at_end'] for x in gone if x.get('her_steps_at_end') is not None)
    walked = {k: total('candidate', 'long_' + k) for k in ('closer', 'same', 'farther', 'no_walk')}
    cpu = {t: ratio(total(t, 'points'), total(t, 'turns'), 1) if total(t, 'points') else None for t in lone}
    wins = both('win')

    def mean(tag, field):
        return ratio(total(tag, field), games, 1)

    failed = [k for k, v in checks.items() if v is False]
    unseen = [k for k, v in checks.items() if v is None]
    verdict = 'PASS (all five checks)' if passed else 'FAIL (' + '; '.join(
        ([f"failed: {', '.join(failed)}"] if failed else []) +
        ([f"could not be judged, too few cases: {', '.join(unseen)}"] if unseen else [])) + ')'
    note = (
        f"{verdict}. {games} paired games, {changed} of them play differently with the switch on; {silent}/{games} "
        f"pairs are the same game until one of ours holds 'our queen is dead' after round 100. Revenge window "
        f"(their queen the only queen for {MIN_WINDOW}+ of her turns from round 100, after one of ours said so by "
        f"sonar): {len(target)} pairs (need {MIN_TARGET_GAMES}). Long turns (hunting on a sighting older than 20 "
        f"rounds): candidate {long_turns['candidate']} in "
        f"{sum(1 for p in pairs if p['candidate']['long_turns'])} games (need {MIN_LONG_TURNS} turns), base "
        f"{long_turns['base']}; the candidate has one in {len(fired)} of the {len(target)} pairs with a revenge "
        f"window (share {fire_share}, need {FIRE_SHARE}); {off_spec['candidate']} long turns break the card's "
        f"rules (round 100, age up to 60, length up to 4, not a queen). Long hunts: {len(hunts)}, ended as "
        f"{ends('candidate', 'long_hunt_ends')}; of the {len(judged)} that ran their course {len(found)} found "
        f"her (share {arrive_share}, need {round(ARRIVE_SHARE, 3)} of at least {MIN_LONG_HUNTS}). On long turns "
        f"the hunter ended closer to her last cell {walked['closer']} times, as close {walked['same']}, farther "
        f"{walked['farther']}, and {walked['no_walk']} times it had no walk to it (another part of the map, only "
        f"a portal leads there). Hunters that reached her last cell and found it "
        f"empty: {len(gone)}; she was then {gone_steps} path steps away. The card's premise, switch off: "
        f"{total('base', 'stale_chances')} revenge hunts ended because the sighting turned 21 rounds old (stale "
        f"chances); all switch-off revenge hunts ended as {ends('base', 'revenge_hunt_ends')}. "
        f"Not gated, the card's signals. Lone turns (her turns from round 100 with our queen dead): base "
        f"{lone['base']} in {len(lone_games['base'])} games, candidate {lone['candidate']} in "
        f"{len(lone_games['candidate'])}. Our heads within {NEAR} path steps of her per lone turn: base "
        f"{near['base']}, candidate {near['candidate']} (card asks for 2); small ones only {near_small['base']} -> "
        f"{near_small['candidate']}; share of lone turns with 2 or more {near2['base']} -> {near2['candidate']}; "
        f"with one of ours next to her {beside['base']} -> {beside['candidate']}. Her mean length on lone turns "
        f"{her_len['base']} -> {her_len['candidate']}. Her deaths on lone turns: base {killed['base']} (head-on "
        f"with one of ours {head_on['base']}), candidate {killed['candidate']} (head-on {head_on['candidate']}, "
        f"{by_long} by a dragon on a long hunt). Their lone queen alive at the end of the games with lone turns "
        f"that went the full 500 rounds: base {alive_end['base']} of {len(full['base'])}, candidate "
        f"{alive_end['candidate']} of {len(full['candidate'])} (card asks for under 0.30). Wrong sign 1, switch "
        f"off: one of ours was next to her on a lone turn and she was still alive at the end in {lived_beside} of "
        f"{len(lone_games['base'])} games. Wrong sign 2, our pearls after round {LATE}: {pearls['base']} -> "
        f"{pearls['candidate']} (change {pearl_change}; more than {PEARL_DROP} down: {pearl_sign}). Cost: hunter "
        f"turns after round {LATE} {total('base', 'hunter_turns_late')} -> {total('candidate', 'hunter_turns_late')} "
        f"of {total('base', 'turns_late')} -> {total('candidate', 'turns_late')} dragon turns; our longest at the "
        f"end {mean('base', 'end_longest_us')} -> {mean('candidate', 'end_longest_us')}, their longest "
        f"{mean('base', 'end_longest_them')} -> {mean('candidate', 'end_longest_them')}; our deaths "
        f"{total('base', 'deaths')} -> {total('candidate', 'deaths')}; wins {wins['base']} -> {wins['candidate']} "
        f"(not a result, {games} pairs); timeouts {total('base', 'tle')} -> {total('candidate', 'tle')}; CPU points "
        f"per turn {cpu['base']} -> {cpu['candidate']} (None = not metered).")
    result = {
        'passed': passed,
        'note': note,
        'mechanism_shown': passed,
        'target_seen': target_seen,
        'fires_as_specified': fires_as_specified,
        'arrives': checks['arrives'],
        'checks': checks,
        'thresholds': {'MIN_WINDOW': MIN_WINDOW, 'MIN_TARGET_GAMES': MIN_TARGET_GAMES, 'FIRE_SHARE': FIRE_SHARE,
                       'MIN_LONG_TURNS': MIN_LONG_TURNS, 'MIN_LONG_HUNTS': MIN_LONG_HUNTS,
                       'ARRIVE_SHARE': ARRIVE_SHARE, 'NEAR': NEAR, 'LATE': LATE, 'PEARL_DROP': PEARL_DROP},
        'built_as': BUILT_AS,
        'games': games,
        'pairs_that_differ': changed,
        'pairs_same_until_switch_can_act': silent,
        'pairs_with_revenge_window': len(target),
        'pairs_with_revenge_window_and_long_turn': len(fired),
        'fire_share': fire_share,
        'lone_turns_after_queen_dead_message': both('lone_turns_known'),
        'stale_chances': both('stale_chances'),
        'games_with_stale_chance': {t: sum(1 for p in pairs if p[t]['stale_chances']) for t in lone},
        'revenge_hunt_ends': {t: ends(t, 'revenge_hunt_ends') for t in lone},
        'long_turns': long_turns,
        'games_with_long_turn': {t: sum(1 for p in pairs if p[t]['long_turns']) for t in lone},
        'long_turns_off_spec': off_spec,
        'long_hunts': both('long_hunts'),
        'long_hunt_ends': ends('candidate', 'long_hunt_ends'),
        'long_hunts_ran_their_course': len(judged),
        'long_hunts_found_her': len(found),
        'arrive_share': arrive_share,
        'long_hunts_next_to_her': sum(1 for x in hunts if x['next_to_her']),
        'long_turns_walk': walked,
        'reached_empty_cell': len(gone),
        'reached_empty_cell_her_path_steps': gone_steps,
        'hunts': both('hunts'),
        'hunt_ends': {t: ends(t, 'hunt_ends') for t in lone},
        'hunter_turns': both('hunter_turns'),
        'revenge_turns': both('revenge_turns'),
        'hunter_turns_on_lone_turns_rounds': both('hunter_turns_lone'),
        'hunter_turns_after_300': both('hunter_turns_late'),
        'dragon_turns_after_300': both('turns_late'),
        'her_death_notices': both('notices'),
        'lone_turns': lone,
        'games_with_lone_turns': {t: len(lone_games[t]) for t in lone},
        'near_heads_per_lone_turn': near,
        'near_small_heads_per_lone_turn': near_small,
        'near_hunting_heads_per_lone_turn': {t: ratio(total(t, 'near_hunting_sum'), lone[t], 2) for t in lone},
        'lone_turns_with_2_near_share': near2,
        'lone_turns_with_ours_next_to_her_share': beside,
        'her_mean_length_on_lone_turns': her_len,
        'her_deaths_on_lone_turns': killed,
        'her_head_on_deaths_with_ours': head_on,
        'her_deaths_by_long_hunter': by_long,
        'lone_games_full_length': {t: len(full[t]) for t in lone},
        'lone_queen_alive_at_end_of_full_games': alive_end,
        'lone_queen_alive_share': alive_share,
        'wrong_sign_next_to_her_and_she_lived_base_games': lived_beside,
        'pearls_after_300': pearls,
        'pearls_after_300_change': pearl_change,
        'wrong_sign_pearls_down_a_tenth': pearl_sign,
        'pearls': both('pearls'),
        'our_deaths': both('deaths'),
        'our_deaths_after_300': both('deaths_late'),
        'wins': wins,
        'end_longest_us_mean': {t: mean(t, 'end_longest_us') for t in lone},
        'end_longest_them_mean': {t: mean(t, 'end_longest_them') for t in lone},
        'end_total_us_mean': {t: mean(t, 'end_total_us') for t in lone},
        'end_total_them_mean': {t: mean(t, 'end_total_them') for t in lone},
        'sonar_messages': both('sonar'),
        'unreadable_own_sonar': both('unreadable'),
        'timeouts': both('tle'),
        'cpu_points_per_turn': cpu,
        'cpu_points_max': {t: max((p[t]['points_max'] for p in pairs), default=0) for t in lone},
        'limits': 'Who hunts is read from the queen pings, so a hunter turn whose ping gave way to a portal warning '
                  'is not seen (one such turn inside a hunt is bridged). "Finds her" is geometry from the replay '
                  '(her head in the 7x7 box at the start of the hunter\'s turn), not the bot\'s own flag. A stale '
                  'chance is only the hunts that visibly ran out at age 20; a dragon holding an old sighting it '
                  'never hunted on is not counted, so the switch can fire without one. The games are our build '
                  'against itself: a queen dies far less often than on the ladder, so revenge windows are rare '
                  'and come from few maps. After the first long turn the two games of a pair drift apart, so '
                  'lone-turn counts, pearls, lengths and deaths compare two different games: with 16 pairs they '
                  'show a direction at best. The ladder figures in the card (1.15 heads, 41 of 102) come from '
                  'other opponents and another script.',
        'pairs': pairs,
    }
    with open(a.output, 'w') as f:
        json.dump(result, f, indent=1)
        f.write('\n')
    print(note)


if __name__ == '__main__':
    main()
