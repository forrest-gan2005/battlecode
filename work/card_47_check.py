#!/usr/bin/env python3
"""Card #47 mechanism check (UPDATE_MAP), second build: a dragon that finds itself in a dead end pings it in all
four directions every turn, a teammate that hears a dead end new to it passes it on once, and a dragon that knows a
dead end with fewer than 2 pearls inside stops treating what is in there as a target and pays 2 lengths to step in.
The first build's split ping (dead end plus pearl spots for the child) is still sent.

usage: python3 work/card_47_check.py --replays DIR --base base --candidate candidate --output FILE
Reads paired replays DIR/<tag>_<map>_<seed>_<side>.replay (side 0 = we are team A).

Words:
  new message    our sonar message of the kind this card adds, read with our codec key. It carries either a dead
                 end (gate tile, direction in, number of tiles, pearls counted inside or "not counted") plus up to
                 two pearl spots, or up to three pearl spots. The count is the sender's "pearls there or due":
                 pearls lying inside, refill tiles, and tiles whose spawn timer is about to run out.
  dead end       on the real map, from a dragon's head and the tile it came from: that tile is the first gate;
                 everything reachable from the head without stepping on the gate must be at most ROOM_MAX tiles
                 with no portal, and may touch the gate on that one side only (a dragon circling in a sealed box
                 is not in a dead end). The gate then moves outwards while it is itself a plain corridor tile
                 (exactly one more way on). This is the bot's own rule run with the whole map known, so the bot
                 (which only knows what it has seen) can report a smaller dead end, or none yet. A shut room big
                 enough to turn around in counts too, as in the first build.
  true dead end  a dead end in a message checked against the real map: past the gate in the stated direction lie
                 exactly the stated number of tiles, shut by kelp, no portal, touching the gate on one side only.
                 "Whole": it is one of the dead ends the rule above finds on the real map (not just the inner
                 part of one).
  stay           one visit: from the step that puts one of our dragons inside a dead end, heading in, until its
                 head leaves that area or it dies.
  wasted stay    the dragon ate fewer than PAY pearls on that stay and split or died inside. PAY is Zhe's line:
                 2 pearls make up for the 2 lengths a dead end costs.
  alert          a new message naming a true dead end that holds the sender's head, on a turn it does not split.
  passed-on copy a new message marked as passed on: a teammate heard a dead end new to it and sent it on.
  way in         one of our dragons steps onto the gate tile of a whole dead end, coming from outside it. It
                 "walked in" when its next step goes inside.
  told           before that step the dragon was hit by a ray carrying exactly that dead end (the replay records
                 which dragon a ray hits), or had sent it itself.
  told, charged  told, and the last pearl count it was given is under PAY, older than FRESH rounds, or missing.
                 These are the arrivals the charge is aimed at. Pearls the dragon sees itself are not in the
                 replay, so some of these were in fact not charged.

Expectation, written before any game of this build with the switch on (thresholds are the constants below).
Reference numbers come from running this same check on the first build's 16 + 16 behaviour-check games (same
four maps, kept in the card's attempt-1 folder); they are quoted in build.json.
  1. alerts fire: base sends no new message; at least ALERT_SHARE of the candidate's stays have an alert.
  2. true: at least TRUE_SHARE of the dead ends carried in candidate messages are true.
  3. reach: at least TOLD_SHARE of the candidate's arrivals at a way in are by a dragon that had been told.
  4. told dragons stay out: with at least MIN_ARRIVALS told-charged and MIN_ARRIVALS untold arrivals, the
     told-charged ones walk in at most HALF as often as the untold ones.
  5. fewer wasted stays: with at least MIN_STAYS wasted stays in base, the candidate has at most DROP times
     base's wasted stays per 1,000 of our dragon turns.
  6. nothing else changes: every pair plays the same game up to the round of the candidate's first new message.
passed = all six. 1, 2 and 6 say "sent, right, and nothing else moved" (fires_as_specified); target_seen says the
games held the case (at least MIN_STAYS stays and MIN_ARRIVALS told-charged arrivals); 3, 4 and 5 say more dragons
know and act on it (behaviour_shown).
Reported, not part of the verdict: alerts per turn inside, passed-on copies and whom they reached, walk-ins by
told-charged dragons with an enemy head near the gate ("dangerous outside"), told dragons with a fresh count of
PAY or more, paid stays (a dead end worth visiting should still be visited), pearls eaten and lengths lost inside,
the split ping of the first build (sent, child told, spots used), and what the messages displace (leader reports,
deaths, timeouts, CPU).
"""
import argparse, concurrent.futures as cf, glob, hashlib, json, os, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

ALERT_SHARE = 0.6
TRUE_SHARE = 0.9
TOLD_SHARE = 0.15
HALF = 0.5
DROP = 0.9
MIN_STAYS = 10
MIN_ARRIVALS = 30
PAY = 2
FRESH = 25
ROOM_MAX = 31
RESEND = 2
WATCH = 30
NEAR = 3
SPOT_SPAN = 32
PEARLS_NONE = 15
LOG_MAX = 60
DIRS = 'NESW'
STEP = {'N': (0, -1), 'E': (1, 0), 'S': (0, 1), 'W': (-1, 0)}
BUILT_AS = (
    "How Zhe's revision (7 Oct) was built on top of the first build. (1) Alert: after its move every dragon checks "
    "whether the tile it came from is the only way out of a shut area of at most 31 tiles around its head (all "
    "sides seen, no portal). If so, all four pings that turn carry the dead end: gate tile, direction in, number of "
    "tiles, and the pearls it counts inside. It does this every turn it is in there, whether or not it can split, "
    "and the leader report waits. It has to see the shut end first, so in a long corridor the first alert goes out "
    "a few tiles in. (2) Cost: a dragon that knows a dead end (told, or found by itself) and is outside it counts "
    "the pearls it knows inside. A count is 'pearls there or due': pearls lying on the tiles, refill tiles (tiles "
    "the bot has watched refill quickly), and tiles whose spawn timer runs out within 6 rounds, so a corridor that "
    "keeps regrowing pearls is not mistaken for an empty one just after somebody ate there. The count it was told "
    "holds for 25 rounds; its own look adds to that only where it is newer, and once the told count is old it goes "
    "by its own look alone. With fewer than 2, nothing inside is a target and a step into it "
    "costs 600 points, the price the bot puts on two pearls eaten, on top of the usual too-little-room penalties. "
    "It is a cost, not a wall: with no better step the dragon still goes in. With 2 or more nothing is added and "
    "the first build's rules decide. Unchanged from the first build: the split ping to the child (dead end first, "
    "then pearl spots), the re-send for 2 turns, and a told dead end being treated as a shut room. Our choices, not "
    "asked by Zhe: (a) passing it on once: a dragon that hears a dead end new to it sends it on that same turn in "
    "all four directions, marked so that the next hearer does not pass it on again; added because in the first "
    "build few dragons reaching a way in had been told; (b) pearl counts: 15 in the count field now means 'not "
    "counted' (a dead end passed on at a split by a dragon that is not looking at it), and such a dead end is "
    "charged unless the hearer sees 2 pearls itself; (c) pearl spots inside a dead end the sender knows are no "
    "longer sent, the count speaks for them; (d) a dragon keeps the 16 dead ends nearest to it (first build: the "
    "last 8 it heard); (e) the dead end may touch its gate on one side only, so a dragon going round in a sealed "
    "box is not 'in a dead end' (in the first build it was, which only mattered on a split turn); (f) counting "
    "pearls that are due, not only pearls lying there; (g) a shut room big enough to turn around in still counts "
    "as a dead end, as in the first build.")

# mybot2/sonar_codec.hpp in Python: the check reads our own messages.
M64 = (1 << 64) - 1
SECRET = 0xE1DE70530C48DE42
CHECK_MASK = 0xFF << 55
TAG_MASK = 0x3 << 53
CIPHER_MASK = M64 & ~(CHECK_MASK | TAG_MASK)
PING_KIND = 0x2B5
MOUTH_KIND = 0xA5


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


def shift(a, b, size):
    raw = (b - a) % size
    return raw - size if raw > size // 2 else raw


def pack_split(tag, W, H, end=None, spots=(), relay=False):
    """end: (gate tile, direction letter, room, pearls or None = not counted) or None. spots: [(tile, refill)], two
    with an end, else three. relay: a passed-on copy (dead end only, no spots)."""
    body = (1 << 52) | ((tag & 0x3) << 53) | (1 << 63)
    if end is not None:
        (gx, gy), way, room, pearls = end
        pearls = PEARLS_NONE if pearls is None else min(pearls, PEARLS_NONE - 1)
        body |= (1 << 51) | (gy * W + gx) | (DIRS.index(way) << 14) | ((room & 0x1F) << 16) | (pearls << 21)
        if relay:
            assert not spots, 'a passed-on copy carries no spots'
            body |= 1 << 37
        for k in range(2):
            (x, y), refill = spots[k] if k < len(spots) else ((gx, gy), False)
            dx, dy = shift(gx, x, W) + SPOT_SPAN, shift(gy, y, H) + SPOT_SPAN
            assert 0 <= dx < 64 and 0 <= dy < 64, 'spot too far from the gate'
            body |= (dx | (dy << 6) | (int(refill) << 12)) << (25 + 13 * k)
    else:
        assert spots, 'nothing to tell'
        for k in range(3):
            (x, y), refill = spots[k] if k < len(spots) else (spots[0][0], False)
            body |= ((y * W + x) | (int(refill) << 14)) << (15 * k)
    return body


def parse(plain, W, H):
    """{'kind': 'split', 'end': {...} or None, 'spots': [(tile, refill)], 'relay': bool} for the new kind; else the
    kind only. In a dead end 'pearls' is None when the sender did not count."""
    body = plain & ((1 << 55) - 1)
    if plain >> 63 == 0:
        return {'kind': 'leader'}
    if (body >> 52) & 1:
        spots = []
        if (body >> 51) & 1:
            gate = body & 0x3FFF
            gx, gy = gate % W, gate // W
            for k in range(2):
                s = body >> (25 + 13 * k)
                dx, dy = (s & 0x3F) - SPOT_SPAN, ((s >> 6) & 0x3F) - SPOT_SPAN
                if dx or dy:
                    spots.append((((gx + dx) % W, (gy + dy) % H), bool((s >> 12) & 1)))
            pearls = (body >> 21) & 0xF
            return {'kind': 'split', 'spots': spots,
                    'relay': (body >> 25) & 0x1FFF == (1 << 12) | (SPOT_SPAN << 6) | SPOT_SPAN,
                    'end': {'gate': (gx, gy), 'dir': DIRS[(body >> 14) & 3], 'room': (body >> 16) & 0x1F,
                            'pearls': None if pearls == PEARLS_NONE else pearls, 'on_map': gate < W * H}}
        first = body & 0x3FFF
        for k in range(3):
            s = body >> (15 * k)
            cell = s & 0x3FFF
            if (k == 0 or cell != first) and cell < W * H:
                spots.append(((cell % W, cell // W), bool((s >> 14) & 1)))
        return {'kind': 'split', 'end': None, 'spots': spots, 'relay': False}
    if (body >> 38) & 0x7FFF == MOUTH_KIND and (body >> 23) & 0x7FFF == 0:
        return {'kind': 'mouth'}
    if (body >> 42) & 0x7FF == PING_KIND:
        return {'kind': 'queen'}
    return {'kind': 'other'}


def read_map(text):
    """Size, starting bodies and tile sides. Side kinds: 0 open, 1 kelp, 2 portal."""
    lines = [line.split() for line in text.splitlines() if line.strip()]
    W, H = map(int, next(q for q in lines if q[0] == 'MAP')[1:3])
    bodies, team_of, kinds = {}, {}, {}

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
            if key is not None:
                kinds[key] = max(kinds.get(key, 0), int(q[2]))
    return W, H, bodies, team_of, kinds


class Board:
    """The real map, and every dead end on it: `gates` maps a gate tile to the whole dead ends behind it."""

    def __init__(self, W, H, kinds):
        self.W, self.H, self.kinds = W, H, kinds
        self.sides, self.memo, self.by_cells = {}, {}, {}
        for y in range(H):
            for x in range(W):
                for _, kind, nxt in self.around((x, y)):
                    if kind == 0:
                        self.dead_end((x, y), nxt)
        self.gates = {}
        for end in self.by_cells.values():
            end['whole'] = True
            self.gates.setdefault(end['gate'], []).append(end)

    def side(self, cell, ch):
        x, y = cell
        key = {'N': (0, x, y), 'S': (0, x, (y + 1) % self.H), 'W': (1, x, y), 'E': (1, (x + 1) % self.W, y)}[ch]
        return self.kinds.get(key, 0)

    def beside(self, cell, ch):
        return (cell[0] + STEP[ch][0]) % self.W, (cell[1] + STEP[ch][1]) % self.H

    def around(self, cell):
        got = self.sides.get(cell)
        if got is None:
            got = self.sides[cell] = tuple((ch, self.side(cell, ch), self.beside(cell, ch)) for ch in DIRS)
        return got

    def shut_area(self, start, gate):
        """Tiles reachable from `start` without stepping on `gate`; None when there are more than ROOM_MAX or a portal."""
        seen, todo = {start}, [start]
        for cell in todo:
            for _, kind, nxt in self.around(cell):
                if kind == 1:
                    continue
                if kind == 2:
                    return None
                if nxt == gate or nxt in seen:
                    continue
                if len(seen) >= ROOM_MAX:
                    return None
                seen.add(nxt)
                todo.append(nxt)
        return seen

    def intern(self, gate, way, cells):
        end = self.by_cells.get(cells)
        if end is None:
            end = self.by_cells[cells] = {'id': len(self.by_cells), 'gate': gate, 'dir': way, 'cells': cells,
                                          'whole': False}
        return end

    def dead_end(self, head, came_from):
        """The bot's dead-end rule with the whole map known: the dead end's record, or None."""
        key = (head, came_from)
        if key in self.memo:
            return self.memo[key]
        inside, at, best = head, came_from, None
        for _ in range(ROOM_MAX + 1):
            cells = self.shut_area(head, at)
            if cells is None:
                break
            way, outs, plain, ring = None, [], True, False
            for ch, kind, nxt in self.around(at):
                if kind == 1:
                    continue
                if kind == 2:
                    plain = False
                    continue
                if nxt == inside:
                    way = ch
                elif nxt not in cells:
                    outs.append(nxt)
                else:
                    ring = True
            if way is None or ring:
                break
            best = (at, way, cells)
            if not plain or len(outs) != 1:
                break
            inside, at = at, outs[0]
        if best is not None:
            best = self.intern(best[0], best[1], frozenset(best[2]))
        self.memo[key] = best
        return best

    def told(self, end):
        """A dead end from a message against the real map: its record when true, else None."""
        if not end['on_map'] or end['room'] <= 0 or self.side(end['gate'], end['dir']) != 0:
            return None
        inner = self.beside(end['gate'], end['dir'])
        cells = self.shut_area(inner, end['gate'])
        if cells is None or len(cells) != end['room']:
            return None
        if any(kind == 0 and nxt != inner and nxt in cells for _, kind, nxt in self.around(end['gate'])):
            return None
        return self.intern(end['gate'], end['dir'], frozenset(cells))


BOARDS = {}


def board_for(text):
    key = hashlib.sha1(text.encode()).hexdigest()
    if key not in BOARDS:
        W, H, _, _, kinds = read_map(text)
        BOARDS[key] = Board(W, H, kinds)
    return BOARDS[key]


def draw(board, end, marks=None):
    """A dead end as text: # inside, G gate, other letters from `marks` {tile: letter}; | and - are kelp."""
    marks = marks or {}
    gate, W, H = end['gate'], board.W, board.H
    lines = []
    for y in range(gate[1] - 6, gate[1] + 7):
        top, mid = '', ''
        for x in range(gate[0] - 9, gate[0] + 10):
            cell = (x % W, y % H)
            top += '+' + ('-' if board.side(cell, 'N') == 1 else ':' if board.side(cell, 'N') == 2 else ' ')
            mark = marks.get(cell) or ('G' if cell == gate else '#' if cell in end['cells'] else '.')
            mid += ('|' if board.side(cell, 'W') == 1 else ':' if board.side(cell, 'W') == 2 else ' ') + mark
        lines += [top, mid]
    return '\n'.join(lines)


STATS = (
    'sonar', 'unreadable', 'leader', 'mouth', 'queen', 'other', 'new_rays', 'turns', 'points', 'points_max', 'tle',
    'deaths', 'splits', 'splits_with_ping', 'splits_resent', 'child_told', 'child_told_on_split_turn',
    'split_turn_any_ray_hit_child', 'end_splits', 'end_splits_with_end', 'spots_told', 'spots_told_refill',
    'spots_stepped', 'spots_grew', 'msgs_with_end', 'msgs_end_true', 'msgs_end_whole', 'msgs_end_counted',
    'alert_turns', 'split_turns_own_end', 'relay_turns', 'passon_turns', 'end_rays', 'end_rays_hit_teammate',
    'relay_rays_hit_teammate', 'first_tellings', 'inside_turns', 'inside_turns_alert', 'inside_quiet_turns',
    'inside_quiet_turns_alert')


def scan(path, ours):
    """One pass over a replay for our side."""
    root = replay.load(path).root()
    text = root.text(0)
    W, H, bodies, team_of, _ = read_map(text)
    board = board_for(text)
    tag = team_tag(ours)
    key, streams, opened, shut = make_key(W, H, tag), {}, {}, {}

    stat = {k: 0 for k in STATS}
    digests, h = {}, hashlib.sha1()
    splits, by_parent, by_child = [], {}, {}
    knows, stays, done, pending, arrivals, named = {}, {}, [], {}, [], set()
    first_new = None
    rnd = 0
    cur = None

    def told_end(end):
        k = (end['gate'], end['dir'], end['room'])
        if k not in shut:
            shut[k] = board.told(end)
        return shut[k]

    def learn(did, end, count):
        """Dragon `did` now knows `end`; a pearl count, when given, is dated this round."""
        known = knows.setdefault(did, {})
        if end['id'] not in known:
            known[end['id']] = [rnd, None, None]
            stat['first_tellings'] += 1
        if count is not None:
            known[end['id']][1:] = [count, rnd]

    def view(did, end):
        """(told, the pearl count it holds while fresh else None)."""
        row = knows.get(did, {}).get(end['id'])
        if row is None:
            return False, None
        return True, row[1] if row[2] is not None and rnd - row[2] <= FRESH else None

    def foe_near(cell):
        for did, body in bodies.items():
            if team_of.get(did) != ours and body and abs(shift(cell[0], body[0][0], W)) <= NEAR and \
                    abs(shift(cell[1], body[0][1], H)) <= NEAR:
                return True
        return False

    def finish(did, how, lost=0):
        s = stays.pop(did)
        s.update(how=how, lost=lost, last_round=rnd)
        done.append(s)

    def on_step(did, grew):
        """After one head move of one of our dragons."""
        body = bodies[did]
        head = body[0]
        prev = body[1] if len(body) > 1 else None
        for a in pending.pop(did, ()):
            a['walked_in'] = head in a['end']['cells']
        s = stays.get(did)
        if s is not None:
            if head in s['end']['cells']:
                s['pearls'] += grew
            else:
                finish(did, 'left')
                s = None
        if prev is not None:
            if s is None:
                end = board.dead_end(head, prev)
                if end is not None:
                    told, count = view(did, end)
                    stays[did] = {'end': end, 'round': rnd, 'dragon': did, 'length': len(body) - grew,
                                  'pearls': int(grew), 'turns': 0, 'alert': False, 'alert_quiet': False, 'splits': 0,
                                  'told': told, 'count': count}
            for end in board.gates.get(head, ()):
                if prev not in end['cells']:
                    told, count = view(did, end)
                    a = {'round': rnd, 'dragon': did, 'end': end, 'told': told, 'count': count,
                         'charged': told and not (count is not None and count >= PAY), 'named': end['id'] in named,
                         'walked_in': False, 'died': False, 'foe_near': foe_near(head), 'length': len(body)}
                    arrivals.append(a)
                    pending.setdefault(did, []).append(a)
        s = by_child.get(did)
        if s is not None and rnd - s['round'] <= WATCH:
            s['gain'] = len(body) - s['child_length']
            for spot in s['spots']:
                if spot['tile'] == head and not spot['stepped']:
                    spot['stepped'], spot['grew'] = True, grew

    def close_turn():
        nonlocal cur, first_new
        if cur is None:
            return
        t, cur = cur, None
        did = t['id']
        body = bodies.get(did)
        head = body[0] if body else None
        now = board.dead_end(body[0], body[1]) if body and len(body) > 1 else None
        sp = by_parent.get(did)
        if sp is not None and sp['round'] == rnd and any(p['hit'] == sp['child'] for p in t['pings']):
            stat['split_turn_any_ray_hit_child'] += 1
        own = relay = passon = False
        counted = set()
        for p in t['pings']:
            stat['sonar'] += 1
            msg = p['msg']
            if msg['kind'] != 'split':
                stat[msg['kind']] += 1
                continue
            stat['new_rays'] += 1
            if first_new is None:
                first_new = rnd
            end = msg['end']
            real = told_end(end) if end is not None else None
            if end is not None and id(msg) not in counted:
                counted.add(id(msg))
                stat['msgs_with_end'] += 1
                stat['msgs_end_true'] += real is not None
                stat['msgs_end_whole'] += real is not None and real['whole']
                stat['msgs_end_counted'] += end['pearls'] is not None
            if real is not None:
                named.add(real['id'])
                inside = head is not None and head in real['cells']
                relay = relay or msg['relay']
                own = own or (inside and not msg['relay'])
                passon = passon or (not inside and not msg['relay'])
                if inside:
                    learn(did, real, end['pearls'])
                stat['end_rays'] += 1
                hit = p['hit']
                if hit is not None and hit != did and team_of.get(hit) == ours:
                    learn(hit, real, end['pearls'])
                    stat['end_rays_hit_teammate'] += 1
                    stat['relay_rays_hit_teammate'] += msg['relay']
            if sp is None or rnd - sp['round'] > RESEND:
                continue
            if rnd == sp['round'] and sp['msg'] is None:
                sp['msg'] = msg
                sp['spots'] = [{'tile': tile, 'refill': refill, 'stepped': False, 'grew': False}
                               for tile, refill in msg['spots']]
            if msg is not sp['msg']:
                continue
            sp['resent'] = sp['resent'] or rnd != sp['round']
            if p['hit'] == sp['child'] and not sp['told']:
                sp['told'], sp['told_round'] = True, rnd
        quiet = not t['split']
        stat['alert_turns'] += own and quiet
        stat['split_turns_own_end'] += own and not quiet
        stat['relay_turns'] += relay
        stat['passon_turns'] += passon
        if now is not None:
            stat['inside_turns'] += 1
            stat['inside_turns_alert'] += own
            stat['inside_quiet_turns'] += quiet
            stat['inside_quiet_turns_alert'] += own and quiet
        s = stays.get(did)
        if s is not None:
            s['turns'] += 1
            s['alert'] = s['alert'] or own
            s['alert_quiet'] = s['alert_quiet'] or (own and quiet)

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
            if team_of.get(did) != ours or did not in bodies:
                continue
            usage = pl.pointer(1)
            points = usage.u64(0) if usage else 0
            stat['turns'] += 1
            stat['points'] += points
            stat['points_max'] = max(stat['points_max'], points)
            stat['tle'] += pl.bit(32)
            cur = {'id': did, 'pings': [], 'split': False}
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            head, tail = replay.point(pl.pointer(0)), replay.point(pl.pointer(1))
            h.update(f'u{did}{head}{tail}'.encode())
            body = bodies.setdefault(did, deque())
            before = len(body)
            moved = not body or body[0] != head
            if moved:
                body.appendleft(head)
            while len(body) > 1 and body[-1] != tail:
                body.pop()
            if moved and team_of.get(did) == ours:
                on_step(did, len(body) > before)
        elif kind == 'dragonSplit':
            parent, child = pl.i32(0), pl.i32(4)
            h.update(f's{parent}{child}'.encode())
            team = ('A', 'B')[pl.u16(8)]
            old = bodies.get(parent, deque())
            bodies[parent] = deque(replay.point(p) for p in pl.pointer(0))
            bodies[child] = deque(replay.point(p) for p in pl.pointer(1))
            team_of[parent] = team_of[child] = team
            if team != ours:
                continue
            stat['splits'] += 1
            if cur is not None and cur['id'] == parent:
                cur['split'] = True
            if parent in stays:
                stays[parent]['splits'] += 1
            end = board.dead_end(old[0], old[1]) if len(old) > 1 else None
            s = {'round': rnd, 'parent': parent, 'child': child, 'child_length': len(bodies[child]),
                 'end': end, 'msg': None, 'spots': [], 'resent': False, 'told': False, 'told_round': None,
                 'gain': 0, 'child_died': None}
            splits.append(s)
            by_parent[parent] = s
            by_child[child] = s
        elif kind == 'dragonDeath':
            did, reason = pl.i32(0), pl.u16(4)
            h.update(f'd{did}{reason}'.encode())
            if team_of.get(did) == ours:
                stat['deaths'] += 1
                for a in pending.pop(did, ()):
                    a['died'] = True
                if did in stays:
                    finish(did, 'died', len(bodies.get(did, ())))
                s = by_child.get(did)
                if s is not None and rnd - s['round'] <= WATCH:
                    s['child_died'] = rnd
            bodies.pop(did, None)
        elif kind == 'sonarPing':
            if cur is None or pl.i32(0) != cur['id']:
                continue
            wire = pl.u64(16)
            if ((wire & TAG_MASK) >> 53) != tag:
                continue
            if wire not in opened:
                plain = unseal(key, wire, streams)
                opened[wire] = parse(plain, W, H) if plain is not None else {'kind': 'unreadable'}
            cur['pings'].append({'msg': opened[wire], 'dir': DIRS[pl.u16(4) % 4],
                                 'hit': pl.i32(12) if pl.u16(6) else None})
    close_turn()
    digests[rnd] = h.hexdigest()
    for did in list(stays):
        finish(did, 'game over')

    for s in splits:
        msg = s['msg']
        stat['end_splits'] += s['end'] is not None
        if msg is None:
            continue
        stat['splits_with_ping'] += 1
        stat['splits_resent'] += s['resent']
        stat['child_told'] += s['told']
        stat['child_told_on_split_turn'] += s['told'] and s['told_round'] == s['round']
        real = told_end(msg['end']) if msg['end'] is not None else None
        stat['end_splits_with_end'] += s['end'] is not None and real is not None and bool(real['cells'] & s['end']['cells'])
        if s['told']:
            stat['spots_told'] += len(s['spots'])
            stat['spots_told_refill'] += sum(p['refill'] for p in s['spots'])
            stat['spots_stepped'] += sum(p['stepped'] for p in s['spots'])
            stat['spots_grew'] += sum(bool(p['grew']) for p in s['spots'])
    stay_rows = [{'round': s['round'], 'dragon': s['dragon'], 'gate': s['end']['gate'], 'dir': s['end']['dir'],
                  'room': len(s['end']['cells']), 'length': s['length'], 'pearls': s['pearls'], 'turns': s['turns'],
                  'alert': s['alert'], 'alert_quiet': s['alert_quiet'], 'splits': s['splits'], 'how': s['how'],
                  'lost': s['lost'], 'told': s['told'], 'count': s['count'], 'last_round': s['last_round']}
                 for s in done]
    arrival_rows = [{'round': a['round'], 'dragon': a['dragon'], 'gate': a['end']['gate'], 'dir': a['end']['dir'],
                     'room': len(a['end']['cells']), 'told': a['told'], 'count': a['count'], 'charged': a['charged'],
                     'named': a['named'], 'walked_in': a['walked_in'], 'died': a['died'], 'foe_near': a['foe_near'],
                     'length': a['length']} for a in arrivals]
    children = [{'told': s['told'], 'pinged': s['msg'] is not None, 'gain': s['gain'],
                 'died': s['child_died'] is not None} for s in splits]
    return {'digests': digests, 'first_new_round': first_new, 'rounds': rnd, **stat,
            'dead_ends_on_map': sum(len(v) for v in board.gates.values()),
            'dead_ends_named': len(named), 'stays': stay_rows, 'arrivals': arrival_rows, 'children': children}


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


def wasted(s):
    return s['pearls'] < PAY and (s['splits'] > 0 or s['how'] == 'died')


def stay_counts(rows, turns):
    bad = [s for s in rows if wasted(s)]
    return {'stays': len(rows), 'with_alert': sum(s['alert_quiet'] for s in rows),
            'with_alert_or_split_ping': sum(s['alert'] for s in rows),
            'wasted': len(bad), 'wasted_per_1000_turns': round(1000 * len(bad) / turns, 3) if turns else None,
            'wasted_by_a_told_dragon': sum(s['told'] for s in bad),
            'paid': sum(s['pearls'] >= PAY for s in rows),
            'under_pay_but_walked_out': sum(s['pearls'] < PAY and not wasted(s) for s in rows),
            'pearls_eaten': sum(s['pearls'] for s in rows), 'splits_inside': sum(s['splits'] for s in rows),
            'died_inside': sum(s['how'] == 'died' for s in rows), 'length_lost_inside': sum(s['lost'] for s in rows),
            'entered_by_a_told_dragon': sum(s['told'] for s in rows)}


def arrival_counts(rows):
    def cut(keep):
        picked = [a for a in rows if keep(a)]
        near = [a for a in picked if a['foe_near']]
        return {'arrivals': len(picked), 'walked_in': sum(a['walked_in'] for a in picked),
                'walk_in_share': ratio(sum(a['walked_in'] for a in picked), len(picked)),
                'enemy_head_near': len(near), 'walked_in_with_enemy_near': sum(a['walked_in'] for a in near)}

    return {'all': cut(lambda a: True), 'told': cut(lambda a: a['told']),
            'told_charged': cut(lambda a: a['charged']),
            'told_count_pays': cut(lambda a: a['told'] and not a['charged']),
            'untold': cut(lambda a: not a['told']),
            'untold_named_earlier': cut(lambda a: not a['told'] and a['named']),
            'at_dead_ends_named_earlier': cut(lambda a: a['named'])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--replays')
    ap.add_argument('--base')
    ap.add_argument('--candidate')
    ap.add_argument('--output')
    ap.add_argument('--scan', nargs='+', help='instead: print the counts of each replay (no verdict)')
    ap.add_argument('--team', default='A', help='our side for --scan')
    ap.add_argument('--draw', type=int, default=0, help='with --scan: draw this many stays per replay')
    a = ap.parse_args()
    if a.scan:
        for path in a.scan:
            s = scan(path, a.team)
            print(os.path.basename(path), {k: s[k] for k in ('rounds', 'turns', 'splits', 'new_rays', 'alert_turns',
                                                             'relay_turns', 'passon_turns', 'inside_turns',
                                                             'inside_turns_alert', 'msgs_with_end', 'msgs_end_true',
                                                             'dead_ends_on_map', 'dead_ends_named')})
            print('  stays', stay_counts(s['stays'], s['turns']))
            print('  arrivals', {k: (v['arrivals'], v['walked_in']) for k, v in arrival_counts(s['arrivals']).items()})
            board = board_for(replay.load(path).root().text(0))
            for row in s['stays'][:a.draw]:
                print(row)
                end = next(e for e in board.gates[tuple(row['gate'])] if e['dir'] == row['dir'])
                print(draw(board, end))
        return
    if not (a.replays and a.base and a.candidate and a.output):
        ap.error('--replays, --base, --candidate and --output are required')
    base, cand = collect(a.replays, a.base), collect(a.replays, a.candidate)
    if not base or set(base) != set(cand):
        sys.exit(f'missing or unpaired replays: base {len(base)}, candidate {len(cand)}, '
                 f'unpaired {sorted(set(base) ^ set(cand))[:5]}')
    keys = sorted(base)
    jobs = [(src[k], 'A' if k[2] == '0' else 'B') for k in keys for src in (base, cand)]
    with cf.ProcessPoolExecutor(int(os.environ.get('WORKERS', '4'))) as pool:
        scans = list(pool.map(job, jobs))

    arms = ('base', 'candidate')
    pairs = []
    for n, k in enumerate(keys):
        b, c = scans[2 * n], scans[2 * n + 1]
        diff = first_diff(b.pop('digests'), c.pop('digests'))
        pairs.append({'map': k[0], 'seed': k[1], 'side': k[2], 'first_diff_round': diff,
                      'silent_ok': diff is None or (c['first_new_round'] is not None and
                                                    diff >= c['first_new_round']),
                      'base': b, 'candidate': c})

    def total(arm, field):
        return sum(int(p[arm][field] or 0) for p in pairs)

    def both(field):
        return {t: total(t, field) for t in arms}

    def rows(arm, field, keep=lambda p: True):
        return [r for p in pairs if keep(p) for r in p[arm][field]]

    games = len(pairs)
    turns = both('turns')
    stays = {t: stay_counts(rows(t, 'stays'), turns[t]) for t in arms}
    arrive = {t: arrival_counts(rows(t, 'arrivals')) for t in arms}
    cand_stays, cand_arrive = stays['candidate'], arrive['candidate']
    alert_share = ratio(cand_stays['with_alert'], cand_stays['stays'])
    with_end, end_true = both('msgs_with_end'), both('msgs_end_true')
    true_share = ratio(end_true['candidate'], with_end['candidate'])
    told_share = ratio(cand_arrive['told']['arrivals'], cand_arrive['all']['arrivals'])
    charged, untold = cand_arrive['told_charged'], cand_arrive['untold']
    enough_arrivals = charged['arrivals'] >= MIN_ARRIVALS and untold['arrivals'] >= MIN_ARRIVALS
    enough_wasted = stays['base']['wasted'] >= MIN_STAYS
    rate = {t: stays[t]['wasted_per_1000_turns'] for t in arms}
    silent = sum(1 for p in pairs if p['silent_ok'])
    checks = {
        'alerts_fire': total('base', 'new_rays') == 0 and alert_share is not None and alert_share >= ALERT_SHARE,
        'true': true_share is not None and true_share >= TRUE_SHARE,
        'reach': told_share is not None and told_share >= TOLD_SHARE,
        'told_stay_out': enough_arrivals and charged['walk_in_share'] <= HALF * untold['walk_in_share'],
        'fewer_wasted_stays': enough_wasted and rate['candidate'] is not None and
                              rate['candidate'] <= DROP * rate['base'],
        'nothing_else_changes': silent == games,
    }
    fires_as_specified = all(checks[k] for k in ('alerts_fire', 'true', 'nothing_else_changes'))
    target_seen = cand_stays['stays'] >= MIN_STAYS and charged['arrivals'] >= MIN_ARRIVALS
    behaviour_shown = all(checks[k] for k in ('reach', 'told_stay_out', 'fewer_wasted_stays'))
    passed = all(checks.values())

    by_map = {}
    for p in pairs:
        row = by_map.setdefault(p['map'], {})
        for t in arms:
            got = row.setdefault(t, {'games': 0, 'turns': 0, 'alert_turns': 0, 'stays': [], 'arrivals': []})
            got['games'] += 1
            got['turns'] += p[t]['turns']
            got['alert_turns'] += p[t]['alert_turns']
            got['stays'] += p[t]['stays']
            got['arrivals'] += p[t]['arrivals']
    for row in by_map.values():
        for t in arms:
            got = row[t]
            counts, ways = stay_counts(got.pop('stays'), got['turns']), arrival_counts(got.pop('arrivals'))
            got.update(stays=counts['stays'], wasted_stays=counts['wasted'], paid_stays=counts['paid'],
                       wasted_per_1000_turns=counts['wasted_per_1000_turns'],
                       arrivals=ways['all']['arrivals'], arrivals_told=ways['told']['arrivals'],
                       walked_in=ways['all']['walked_in'], told_charged=ways['told_charged']['arrivals'],
                       told_charged_walked_in=ways['told_charged']['walked_in'])

    def growth(arm, keep=lambda r: True):
        picked = [r for r in rows(arm, 'children') if keep(r)]
        return {'children': len(picked), 'mean_gain': ratio(sum(r['gain'] for r in picked), len(picked)),
                'died': sum(r['died'] for r in picked)}

    child_rounds = {'base': growth('base'), 'candidate_told': growth('candidate', lambda r: r['told']),
                    'candidate_not_told': growth('candidate', lambda r: not r['told'])}
    log = []
    for p in pairs:
        name = f"candidate_{p['map']}_{p['seed']}_{p['side']}.replay"
        for arow in p['candidate']['arrivals']:
            if arow['charged'] and len(log) < LOG_MAX:
                log.append({'replay': name, 'what': 'told-charged dragon at a way in', **arow})
    cpu = {t: ratio(total(t, 'points'), turns[t]) if total(t, 'points') else None for t in arms}
    failed = [k for k, v in checks.items() if not v]
    note = (
        f"{'PASS' if passed else 'FAIL'} ({'all six checks' if passed else 'failed: ' + ', '.join(failed)}). "
        f"{games} paired games. Stays in a dead end: base {stays['base']['stays']}, candidate "
        f"{cand_stays['stays']}; candidate stays with an alert {cand_stays['with_alert']} (share {alert_share}); "
        f"base rays of the new kind {total('base', 'new_rays')}. Turns inside a dead end without a split: "
        f"{total('candidate', 'inside_quiet_turns')}, with an alert "
        f"{total('candidate', 'inside_quiet_turns_alert')}. Candidate turns with an alert "
        f"{total('candidate', 'alert_turns')}, with a passed-on copy {total('candidate', 'relay_turns')}, with a "
        f"dead end handed on at a split {total('candidate', 'passon_turns')}. Dead ends carried in messages "
        f"{with_end['candidate']}, true {end_true['candidate']} (share {true_share}), whole "
        f"{total('candidate', 'msgs_end_whole')}, with a pearl count {total('candidate', 'msgs_end_counted')}. Rays "
        f"with a true dead end {total('candidate', 'end_rays')}, hit a teammate "
        f"{total('candidate', 'end_rays_hit_teammate')} ({total('candidate', 'relay_rays_hit_teammate')} of them "
        f"passed-on copies); dragons told a dead end for the first time {total('candidate', 'first_tellings')}. "
        f"Arrivals at a way in: base {arrive['base']['all']['arrivals']} (walked in "
        f"{arrive['base']['all']['walked_in']}, share {arrive['base']['all']['walk_in_share']}), candidate "
        f"{cand_arrive['all']['arrivals']} (walked in {cand_arrive['all']['walked_in']}, share "
        f"{cand_arrive['all']['walk_in_share']}). Candidate arrivals by a told dragon "
        f"{cand_arrive['told']['arrivals']} (share {told_share}). Told and charged: {charged['arrivals']} arrivals, "
        f"walked in {charged['walked_in']} (share {charged['walk_in_share']}), "
        f"{charged['walked_in_with_enemy_near']} of those with an enemy head within {NEAR} tiles of the gate; "
        f"untold: {untold['arrivals']} arrivals, walked in {untold['walked_in']} (share "
        f"{untold['walk_in_share']}); told with a fresh count of {PAY} or more: "
        f"{cand_arrive['told_count_pays']['arrivals']} arrivals, walked in "
        f"{cand_arrive['told_count_pays']['walked_in']}"
        f"{'' if enough_arrivals else ' (too few arrivals to compare: need ' + str(MIN_ARRIVALS) + ' of each)'}. "
        f"Wasted stays (fewer than {PAY} pearls eaten, then split or died inside): base "
        f"{stays['base']['wasted']} ({rate['base']} per 1,000 of our dragon turns), candidate "
        f"{cand_stays['wasted']} ({rate['candidate']}), {cand_stays['wasted_by_a_told_dragon']} of the "
        f"candidate's by a dragon that had been told"
        f"{'' if enough_wasted else ' (too few in base to compare: need ' + str(MIN_STAYS) + ')'}; paid stays: "
        f"base {stays['base']['paid']}, candidate {cand_stays['paid']}; pearls eaten on stays "
        f"{stays['base']['pearls_eaten']} -> {cand_stays['pearls_eaten']}, lengths lost inside "
        f"{stays['base']['length_lost_inside']} -> {cand_stays['length_lost_inside']}. Same game up to the first "
        f"new message in {silent}/{games} pairs. Split ping of the first build: our splits "
        f"{total('candidate', 'splits')}, with a ping on the split turn {total('candidate', 'splits_with_ping')}, "
        f"child told {total('candidate', 'child_told')}; pearl spots told to a child "
        f"{total('candidate', 'spots_told')}, stepped on {total('candidate', 'spots_stepped')}, eaten at "
        f"{total('candidate', 'spots_grew')}. Cost: leader reports {total('base', 'leader')} -> "
        f"{total('candidate', 'leader')}, our deaths {total('base', 'deaths')} -> {total('candidate', 'deaths')}, "
        f"our dragon turns {turns['base']} -> {turns['candidate']}, timeouts {total('base', 'tle')} -> "
        f"{total('candidate', 'tle')}, CPU points per turn {cpu['base']} -> {cpu['candidate']} (None = not "
        f"metered). Per map, candidate (stays / wasted / arrivals / told / told-charged walked in of told-charged, "
        f"base wasted in brackets): " +
        '; '.join(f"{m} {r['candidate']['stays']} / {r['candidate']['wasted_stays']} / "
                  f"{r['candidate']['arrivals']} / {r['candidate']['arrivals_told']} / "
                  f"{r['candidate']['told_charged_walked_in']} of {r['candidate']['told_charged']} "
                  f"[{r['base']['wasted_stays']}]" for m, r in sorted(by_map.items())) + '.')
    for p in pairs:
        for t in arms:
            for field in ('stays', 'arrivals', 'children'):
                p[t][field + '_count'] = len(p[t].pop(field))
    result = {
        'passed': passed,
        'note': note,
        'fires_as_specified': fires_as_specified,
        'target_seen': target_seen,
        'behaviour_shown': behaviour_shown,
        'checks': checks,
        'thresholds': {'ALERT_SHARE': ALERT_SHARE, 'TRUE_SHARE': TRUE_SHARE, 'TOLD_SHARE': TOLD_SHARE, 'HALF': HALF,
                       'DROP': DROP, 'MIN_STAYS': MIN_STAYS, 'MIN_ARRIVALS': MIN_ARRIVALS, 'PAY': PAY, 'FRESH': FRESH,
                       'ROOM_MAX': ROOM_MAX, 'RESEND': RESEND, 'WATCH': WATCH, 'NEAR': NEAR},
        'built_as': BUILT_AS,
        'games': games,
        'our_dragon_turns': turns,
        'stays': stays,
        'alert_share_of_stays': alert_share,
        'turns_inside_a_dead_end': both('inside_turns'),
        'turns_inside_with_own_dead_end_sent': both('inside_turns_alert'),
        'turns_inside_without_split': both('inside_quiet_turns'),
        'turns_inside_without_split_with_alert': both('inside_quiet_turns_alert'),
        'alert_turns': both('alert_turns'),
        'split_turns_with_own_dead_end': both('split_turns_own_end'),
        'passed_on_copy_turns': both('relay_turns'),
        'handed_on_at_split_turns': both('passon_turns'),
        'new_rays': both('new_rays'),
        'messages_with_dead_end': with_end,
        'messages_dead_end_true': end_true,
        'messages_dead_end_whole': both('msgs_end_whole'),
        'messages_dead_end_with_count': both('msgs_end_counted'),
        'true_share': true_share,
        'rays_with_true_dead_end': both('end_rays'),
        'rays_with_true_dead_end_hit_teammate': both('end_rays_hit_teammate'),
        'passed_on_rays_hit_teammate': both('relay_rays_hit_teammate'),
        'dragons_told_a_dead_end_first_time': both('first_tellings'),
        'arrivals_at_a_way_in': arrive,
        'told_share_of_arrivals': told_share,
        'wasted_stays_per_1000_turns': rate,
        'pairs_same_until_first_new_message': silent,
        'by_map': by_map,
        'split_ping': {'our_splits': both('splits'), 'with_ping_on_split_turn': both('splits_with_ping'),
                       'resent': both('splits_resent'), 'child_told': both('child_told'),
                       'child_told_on_split_turn': both('child_told_on_split_turn'),
                       'any_split_turn_ray_hit_child': both('split_turn_any_ray_hit_child'),
                       'dead_end_splits': both('end_splits'),
                       'dead_end_splits_with_dead_end_in_ping': both('end_splits_with_end'),
                       'spots_told_to_child': both('spots_told'), 'of_them_refill': both('spots_told_refill'),
                       'spots_stepped_on': both('spots_stepped'), 'spots_eaten_at': both('spots_grew'),
                       'child_first_rounds': child_rounds},
        'our_deaths': both('deaths'),
        'sonar_messages': both('sonar'),
        'leader_messages': both('leader'),
        'mouth_messages': both('mouth'),
        'queen_pings': both('queen'),
        'other_messages': both('other'),
        'unreadable_own_sonar': both('unreadable'),
        'timeouts': both('tle'),
        'cpu_points_per_turn': cpu,
        'cpu_points_max': {t: max((p[t]['points_max'] for p in pairs), default=0) for t in arms},
        'told_charged_arrivals_log': log,
        'limits': 'Dead ends are rebuilt from the real map with the bot\'s rule; what a dragon actually knew or '
                  'decided is not in the replay, only where it went and which dragon each ray hit. "Told" does not '
                  'mean it still remembers (a dragon keeps 8 dead ends). Pearls on the ground are not read from the '
                  'replay, only growth: "told, charged" is judged from the count in the messages, so a dragon that '
                  'saw 2 pearls itself and was not charged is still counted there, and "wasted" is what a dragon '
                  'ate, not what lay there. Told and untold dragons are different dragons in different places, so '
                  'their walk-in shares are a comparison, not an experiment. Base and candidate stop being the '
                  'same game after the first new message, so the two columns are totals over different games. A '
                  'dragon kept out of a dead end also misses the pearls in it, which is why paid stays and pearls '
                  'eaten are shown next to the wasted ones. Small counts say little.',
        'pairs': pairs,
    }
    with open(a.output, 'w') as f:
        json.dump(result, f, indent=1)
        f.write('\n')
    print(note)


if __name__ == '__main__':
    main()
