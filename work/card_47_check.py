#!/usr/bin/env python3
"""Card #47 mechanism check (UPDATE_MAP): a dragon that splits pings the dead end it stands in and pearl spots near
its child back at the child; any teammate that hears the ping adds both to its map.

usage: python3 work/card_47_check.py --replays DIR --base base --candidate candidate --output FILE
Reads paired replays DIR/<tag>_<map>_<seed>_<side>.replay (side 0 = we are team A).

Words:
  split ping     our sonar message of the new kind, read with our codec key. It carries either a dead end (gate
                 tile, direction in, number of tiles, pearls inside) plus up to two pearl spots, or up to three
                 pearl spots. A spot is marked "refill" (a tile the sender watched refill quickly) or "pearl" (a
                 pearl lying there when the sender last looked).
  dead end       seen from the splitting dragon's head on the real map: the tile it came from is the first gate;
                 everything reachable from the head without stepping on the gate must be at most ROOM_MAX tiles
                 with no portal. The gate then moves outwards while it is itself a plain corridor tile (exactly
                 one more way on). This is the bot's own rule run with the whole map known, so the bot (which
                 only knows what it has seen) can report a smaller dead end or none.
  dead-end split one of our splits where such a dead end exists.
  told           the split has a split ping (sent on the split turn, or re-sent by the parent in the next
                 RESEND rounds) and one of those rays hit the child (the replay records which dragon a ray hits).
  true dead end  a dead end in a ping checked against the real map: past the gate in the stated direction lie
                 exactly the stated number of tiles, shut by kelp, no portal.
  passed on      a ping whose (true) dead end does not hold the parent's head: one she knew, not one she is in.
  repeat         a dead-end split in a dead end our side has already split in earlier in the same game.
  unpaid         the splitting dragon ate fewer than PAID pearls on that stay (since its head last came into the
                 dead end, or since it was born inside). PAID is Zhe's rule of thumb: a visit pays when the pearls
                 eaten outweigh the 2 tiles left behind by the split.
  walked back in the child's head stands inside the split's dead end again, after having been outside it (or
                 from birth outside it), within WATCH rounds of the split. "Same mistake": it then died or had to
                 split while still inside, within WATCH + STUCK rounds of the split.

Expectation, written before any switch-on game was played (thresholds are the constants below). The base numbers
quoted in the build notes come from the switch-off identity games (old 10 maps), which is also how the mechanism
maps were picked: old maps where base often splits in a dead end (trauma, prisoners_dilemma_v0, schooltime,
portals_v0). slithery_fight_v0 has more such splits but was left out: a team splits about 1,500 times a game
there, which would be over half of all splits in the run and decide every share on its own.
  1. fires: at least FIRE_SHARE of the candidate's splits send a split ping on the split turn; base sends none.
  2. reach: of the candidate's splits with a split ping, at least REACH_SHARE are told (a ray hit the child).
  3. true: at least TRUE_SHARE of the dead ends carried in pings are true dead ends.
  4. dead ends seen: the candidate games hold at least MIN_ENDS dead-end splits, and at least END_SHARE of them
     carry a dead end in their ping.
  5. nothing else changes: every pair plays the same game up to the round of the candidate's first split ping.
  6. behaviour: with at least MIN_ENDS unpaid repeats in base, unpaid repeats as a share of our splits are lower
     in the candidate than in base.
passed = all six. 1, 2, 3 and 5 say "the ping is sent, arrives and is right" (fires_as_specified); 4 says the
games held the case the card is about (target_seen); 6 says dragons act on it (behaviour_shown).
Reported, not part of the verdict: paid repeats (a dead end worth visiting should still be visited), dead-end
splits by a dragon that had been told that very dead end, children that walked back in, what told children did
with pearl spots (stepped on the tile, grew there), child growth and deaths in the first WATCH rounds, how many
other teammates a ping reached, how often any split-turn ray hits the child (the ceiling for "told" without
re-sends), and what the ping displaces (leader messages, deaths, timeouts, CPU).
"""
import argparse, concurrent.futures as cf, glob, hashlib, json, os, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

FIRE_SHARE = 0.5
REACH_SHARE = 0.5
TRUE_SHARE = 0.9
MIN_ENDS = 10
END_SHARE = 0.7
PAID = 3
ROOM_MAX = 31
RESEND = 2
WATCH = 30
STUCK = 15
SPOT_SPAN = 32
LOG_MAX = 40
DIRS = 'NESW'
STEP = {'N': (0, -1), 'E': (1, 0), 'S': (0, 1), 'W': (-1, 0)}
BUILT_AS = (
    "How Zhe's answers were built. On the turn a dragon splits it sends one message in all four directions (the "
    "copy sent into its own neck leaves from its tail tip, which is where the child is when the body is straight "
    "there). Dead end first: if the tile the parent came from is the only way out of a shut area of at most 31 "
    "tiles around her head, she sends the gate tile, the direction in, the number of tiles and the number of pearls "
    "she knows inside, and two pearl spots; with no dead end she sends three spots. Spots are refill tiles first, "
    "then pearls on the ground the child cannot see from its own head, nearest to the child first; she keeps the "
    "spot nearest to her own head when she is nearer to it than the child. The leader report is back the turn "
    "after. If no copy was aimed at the child on the split turn, she re-sends for 2 more turns, only in a direction "
    "that is lined up with the child. Whoever hears it (child or any teammate) adds the spots to its map and lets "
    "the normal scoring choose; a told pearl on the ground is ignored where the hearer looked itself in the last 25 "
    "rounds. A told dead end is treated like one the hearer sees: past the gate there are only that many tiles, so "
    "the usual too-little-room penalties apply, and the usual harvest rule (enough pearls inside to pay for a "
    "split) can still send a small dragon in; the told pearl count is used for 25 rounds. Our choices, not asked "
    "by Zhe: (a) a portal-mouth warning keeps its direction on a split turn; (b) with a dead end, spots are sent as "
    "offsets from the gate, so only spots within 32 tiles of it fit; (c) a dragon keeps the last 8 dead ends it "
    "found or was told; (d) a newborn that does not know its whole body yet sends the ping without aiming or "
    "re-sending; (e) passing it on: a dragon that splits outside any dead end sends the nearest dead end it knows "
    "(within 16 tiles of the child, no pearl count) in the dead-end slot. (e) was added because in base games the "
    "child itself rarely walks back in, while most dead-end splits happen in a dead end our side already split in, "
    "by later dragons the first ping never reaches.")

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


def pack_split(tag, W, H, end=None, spots=()):
    """end: (gate tile, direction letter, room, pearls) or None. spots: [(tile, refill)], two with an end, else three."""
    body = (1 << 52) | ((tag & 0x3) << 53) | (1 << 63)
    if end is not None:
        (gx, gy), way, room, pearls = end
        body |= (1 << 51) | (gy * W + gx) | (DIRS.index(way) << 14) | ((room & 0x1F) << 16) | ((pearls & 0xF) << 21)
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
    """{'kind': 'split', 'end': {...} or None, 'spots': [(tile, refill)]} for the new kind; else the kind only."""
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
            return {'kind': 'split', 'spots': spots,
                    'end': {'gate': (gx, gy), 'dir': DIRS[(body >> 14) & 3], 'room': (body >> 16) & 0x1F,
                            'pearls': (body >> 21) & 0xF, 'on_map': gate < W * H}}
        first = body & 0x3FFF
        for k in range(3):
            s = body >> (15 * k)
            cell = s & 0x3FFF
            if (k == 0 or cell != first) and cell < W * H:
                spots.append(((cell % W, cell // W), bool((s >> 14) & 1)))
        return {'kind': 'split', 'end': None, 'spots': spots}
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
    def __init__(self, W, H, kinds):
        self.W, self.H, self.kinds = W, H, kinds

    def side(self, cell, ch):
        x, y = cell
        key = {'N': (0, x, y), 'S': (0, x, (y + 1) % self.H), 'W': (1, x, y), 'E': (1, (x + 1) % self.W, y)}[ch]
        return self.kinds.get(key, 0)

    def beside(self, cell, ch):
        return (cell[0] + STEP[ch][0]) % self.W, (cell[1] + STEP[ch][1]) % self.H

    def shut_area(self, start, gate):
        """Tiles reachable from `start` without stepping on `gate`; None when there are more than ROOM_MAX or a portal."""
        seen, todo = {start}, deque([start])
        while todo:
            cell = todo.popleft()
            for ch in DIRS:
                kind = self.side(cell, ch)
                if kind == 1:
                    continue
                if kind == 2:
                    return None
                nxt = self.beside(cell, ch)
                if nxt == gate or nxt in seen:
                    continue
                if len(seen) >= ROOM_MAX:
                    return None
                seen.add(nxt)
                todo.append(nxt)
        return seen

    def dead_end(self, head, came_from):
        """The bot's dead-end rule with the whole map known: {'gate', 'dir', 'cells'} or None."""
        inside, at, best = head, came_from, None
        for _ in range(ROOM_MAX + 1):
            cells = self.shut_area(head, at)
            if cells is None:
                break
            way, outs, plain = None, [], True
            for ch in DIRS:
                kind = self.side(at, ch)
                if kind == 1:
                    continue
                if kind == 2:
                    plain = False
                    continue
                nxt = self.beside(at, ch)
                if nxt == inside:
                    way = ch
                elif nxt not in cells:
                    outs.append(nxt)
            if way is None:
                break
            best = {'gate': at, 'dir': way, 'cells': cells}
            if not plain or len(outs) != 1:
                break
            inside, at = at, outs[0]
        return best

    def told_true(self, end):
        """A dead end from a ping against the real map."""
        if not end['on_map'] or end['room'] <= 0 or self.side(end['gate'], end['dir']) != 0:
            return False
        cells = self.shut_area(self.beside(end['gate'], end['dir']), end['gate'])
        return cells is not None and len(cells) == end['room']


def draw(path, row):
    """A dead end from a scan's log as text: # inside, G gate, H the parent's head, C the child's head; | and - are kelp."""
    W, H, _, _, kinds = read_map(replay.load(path).root().text(0))
    board = Board(W, H, kinds)
    gate, head, child = tuple(row['gate']), tuple(row['head']), tuple(row['child_head'])
    cells = board.shut_area(head, gate) or set()
    lines = []
    for y in range(gate[1] - 6, gate[1] + 7):
        top, mid = '', ''
        for x in range(gate[0] - 9, gate[0] + 10):
            cell = (x % W, y % H)
            top += '+' + ('-' if board.side(cell, 'N') == 1 else ':' if board.side(cell, 'N') == 2 else ' ')
            mark = 'H' if cell == head else 'G' if cell == gate else 'C' if cell == child else '#' if cell in cells else '.'
            mid += ('|' if board.side(cell, 'W') == 1 else ':' if board.side(cell, 'W') == 2 else ' ') + mark
        lines += [top, mid]
    return '\n'.join(lines)


def scan(path, ours):
    """One pass over a replay for our side."""
    root = replay.load(path).root()
    W, H, bodies, team_of, kinds = read_map(root.text(0))
    board = Board(W, H, kinds)
    tag = team_tag(ours)
    key, streams, opened = make_key(W, H, tag), {}, {}

    stat = {k: 0 for k in (
        'sonar', 'unreadable', 'leader', 'mouth', 'queen', 'other', 'split_rays', 'turns', 'points', 'points_max',
        'tle', 'deaths', 'splits', 'splits_with_ping', 'splits_resent', 'told', 'told_on_split_turn',
        'rays_hit_child', 'rays_hit_other_ally', 'pings_with_end', 'pings_end_true', 'pings_spots',
        'pings_spots_refill', 'end_splits', 'end_splits_with_end', 'end_splits_told', 'stray_split_rays',
        'split_turn_any_ray_hit_child', 'pings_end_passed_on')}
    digests, h = {}, hashlib.sha1()
    splits, by_parent, by_child, log = [], {}, {}, []
    born, steps, visits, knows, shut = {}, {}, {}, {}, {}
    first_ping = None
    rnd = 0
    cur = None

    def told_cells(end):
        """Tiles of a dead end named in a ping (None when it is not a true one)."""
        key = (end['gate'], end['dir'], end['room'])
        if key not in shut:
            shut[key] = (frozenset(board.shut_area(board.beside(end['gate'], end['dir']), end['gate']))
                         if board.told_true(end) else None)
        return shut[key]

    def watch(did, grew):
        """Follow a child after one of its head moves (or its death / own split when grew is None)."""
        s = by_child.get(did)
        if s is None or rnd - s['round'] > WATCH + STUCK:
            return
        body = bodies.get(did)
        if grew is None:
            if s['back_in'] and s['inside'] and not s['stuck']:
                s['stuck'] = True
            return
        head = body[0]
        if rnd - s['round'] <= WATCH:
            s['gain'] = len(body) - s['child_length']
            for spot in s['spots']:
                if spot['tile'] == head and not spot['stepped']:
                    spot['stepped'] = True
                    spot['grew'] = grew
        if s['cells'] is None:
            return
        inside = head in s['cells']
        if not inside:
            s['was_out'] = True
        elif s['was_out'] and not s['back_in'] and rnd - s['round'] <= WATCH:
            s['back_in'] = True
            s['back_round'] = rnd
        if inside and s['back_in'] and grew:
            s['grew_inside'] += 1
        s['inside'] = inside

    def close_turn():
        nonlocal cur, first_ping
        if cur is None:
            return
        t, cur = cur, None
        did = t['id']
        mine = by_parent.get(did)
        if mine is not None and mine['round'] == rnd and any(p['hit'] == mine['child'] for p in t['pings']):
            stat['split_turn_any_ray_hit_child'] += 1
        for p in t['pings']:
            stat['sonar'] += 1
            kind = p['msg']['kind']
            if kind != 'split':
                stat[kind] += 1
                continue
            stat['split_rays'] += 1
            if first_ping is None:
                first_ping = rnd
            s = by_parent.get(did)
            if s is None or rnd - s['round'] > RESEND:
                stat['stray_split_rays'] += 1
                continue
            if s['msg'] is None:
                s['msg'] = p['msg']
                s['spots'] = [{'tile': tile, 'refill': refill, 'stepped': False, 'grew': False}
                              for tile, refill in p['msg']['spots']]
            s['rays'].append({'round': rnd, 'dir': p['dir'], 'hit': p['hit']})
            if p['hit'] is not None and team_of.get(p['hit']) == ours and p['msg']['end'] is not None:
                cells = told_cells(p['msg']['end'])
                if cells is not None:
                    knows.setdefault(p['hit'], set()).add(cells)
            if rnd == s['round']:
                s['sent_on_split_turn'] = True
            else:
                s['resent'] = True
            if p['hit'] == s['child']:
                stat['rays_hit_child'] += 1
                if not s['told']:
                    s['told'] = True
                    s['told_round'] = rnd
            elif p['hit'] is not None and team_of.get(p['hit']) == ours:
                stat['rays_hit_other_ally'] += 1

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
            cur = {'id': did, 'pings': []}
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
                steps.setdefault(did, deque(maxlen=4 * ROOM_MAX)).append((head, len(body) > before))
                watch(did, len(body) > before)
        elif kind == 'dragonSplit':
            parent, child = pl.i32(0), pl.i32(4)
            h.update(f's{parent}{child}'.encode())
            team = ('A', 'B')[pl.u16(8)]
            old = bodies.get(parent, deque())
            if team == ours:
                watch(parent, None)
            bodies[parent] = deque(replay.point(p) for p in pl.pointer(0))
            bodies[child] = deque(replay.point(p) for p in pl.pointer(1))
            team_of[parent] = team_of[child] = team
            if team != ours:
                continue
            stat['splits'] += 1
            end = board.dead_end(old[0], old[1]) if len(old) > 1 else None
            s = {'round': rnd, 'parent': parent, 'child': child, 'parent_length': len(old),
                 'child_length': len(bodies[child]), 'head': old[0], 'child_head': bodies[child][0],
                 'cells': end['cells'] if end else None, 'gate': end['gate'] if end else None,
                 'dir': end['dir'] if end else None, 'room': len(end['cells']) if end else None,
                 'msg': None, 'rays': [], 'sent_on_split_turn': False, 'resent': False, 'told': False,
                 'told_round': None, 'spots': [], 'gain': 0, 'child_died': None,
                 'was_out': False, 'inside': False, 'back_in': False, 'back_round': None, 'stuck': False,
                 'grew_inside': 0}
            if end:
                s['inside'] = s['born_inside'] = bodies[child][0] in end['cells']
                s['was_out'] = not s['inside']
                # This stay in the dead end: steps and pearls since the head last came in (or since birth inside).
                stay = pearls = 0
                for cell, grew in reversed(steps.get(parent, ())):
                    if cell not in end['cells']:
                        break
                    stay += 1
                    pearls += grew
                area = frozenset(end['cells'])
                s.update(stay=stay, stay_pearls=pearls, earlier_here=visits.get(area, 0), kept=len(bodies[parent]),
                         parent_knew=any(old[0] in cells for cells in knows.get(parent, ())),
                         parent_born=born.get(parent))
                visits[area] = visits.get(area, 0) + 1
            born[child] = (rnd, parent)
            splits.append(s)
            by_parent[parent] = s
            by_child[child] = s
        elif kind == 'dragonDeath':
            did, reason = pl.i32(0), pl.u16(4)
            h.update(f'd{did}{reason}'.encode())
            if team_of.get(did) == ours:
                stat['deaths'] += 1
                watch(did, None)
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

    for s in splits:
        msg = s['msg']
        has_end = s['cells'] is not None
        stat['end_splits'] += has_end
        if msg is not None:
            stat['splits_with_ping'] += s['sent_on_split_turn']
            stat['splits_resent'] += s['resent']
            stat['told'] += s['told']
            stat['told_on_split_turn'] += s['told'] and s['told_round'] == s['round']
            stat['pings_spots'] += len(msg['spots'])
            stat['pings_spots_refill'] += sum(1 for _, refill in msg['spots'] if refill)
            if msg['end'] is not None:
                stat['pings_with_end'] += 1
                cells = told_cells(msg['end'])
                s['end_true'] = cells is not None
                s['end_passed_on'] = cells is not None and s['head'] not in cells
                stat['pings_end_true'] += s['end_true']
                stat['pings_end_passed_on'] += s['end_passed_on']
                stat['end_splits_with_end'] += has_end
        stat['end_splits_told'] += has_end and s['told']
        s['cells'] = sorted(s['cells']) if has_end else None
        if len(log) < LOG_MAX and (has_end or (msg is not None and msg['end'] is not None)):
            log.append({k: s.get(k) for k in (
                'round', 'parent', 'child', 'parent_length', 'child_length', 'head', 'child_head', 'gate', 'dir',
                'room', 'msg', 'end_true', 'end_passed_on', 'rays', 'told', 'born_inside', 'back_in', 'back_round', 'stuck',
                'grew_inside', 'gain', 'child_died', 'stay', 'stay_pearls', 'earlier_here', 'kept', 'parent_knew',
                'parent_born')})
    rows = [{k: s.get(k) for k in ('round', 'child_length', 'told', 'gain', 'child_died', 'back_in', 'stuck',
                                    'grew_inside', 'born_inside', 'stay_pearls', 'earlier_here', 'kept',
                                    'parent_knew')} |
            {'dead_end': s['cells'] is not None, 'pinged': s['msg'] is not None,
             'spots': [{'refill': p['refill'], 'stepped': p['stepped'], 'grew': p['grew']} for p in s['spots']]}
            for s in splits]
    return {'digests': digests, 'first_ping_round': first_ping, 'rounds': rnd, **stat, 'splits_rows': rows,
            'dead_end_log': log}


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
    ap.add_argument('--replays')
    ap.add_argument('--base')
    ap.add_argument('--candidate')
    ap.add_argument('--output')
    ap.add_argument('--scan', nargs='+', help='instead: print one line of counts per replay (no verdict)')
    ap.add_argument('--team', default='A', help='our side for --scan')
    ap.add_argument('--draw', type=int, default=0,
                    help='with --scan: draw this many dead-end splits per replay (negative: list them without a drawing)')
    a = ap.parse_args()
    if a.scan:
        for path in a.scan:
            s = scan(path, a.team)
            walked = [r for r in s['splits_rows'] if r['dead_end']]
            print(os.path.basename(path), {k: s[k] for k in ('rounds', 'splits', 'split_turn_any_ray_hit_child',
                                                             'end_splits', 'split_rays', 'sonar', 'leader', 'mouth',
                                                             'queen', 'other', 'unreadable')},
                  'dead-end children walked back in', sum(r['back_in'] for r in walked), 'stuck again',
                  sum(r['stuck'] for r in walked), 'born inside', sum(bool(r['born_inside']) for r in walked),
                  'in a dead end split in before', sum(r['earlier_here'] > 0 for r in walked),
                  'ate 3+ on that stay', sum(r['stay_pearls'] >= 3 for r in walked),
                  'parent kept 2', sum(r['kept'] == 2 for r in walked))
            for row in s['dead_end_log'][:abs(a.draw)]:
                if row['gate'] is not None:
                    print({k: row[k] for k in ('round', 'parent', 'child', 'parent_length', 'child_length', 'room',
                                               'gate', 'dir', 'born_inside', 'back_in', 'stuck', 'told', 'stay',
                                               'stay_pearls', 'earlier_here', 'kept', 'parent_knew', 'parent_born')})
                    if a.draw > 0:
                        print(draw(path, row))
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

    pairs = []
    for n, k in enumerate(keys):
        b, c = scans[2 * n], scans[2 * n + 1]
        diff = first_diff(b.pop('digests'), c.pop('digests'))
        pairs.append({'map': k[0], 'seed': k[1], 'side': k[2], 'first_diff_round': diff,
                      'silent_ok': diff is None or (c['first_ping_round'] is not None and
                                                    diff >= c['first_ping_round']),
                      'base': b, 'candidate': c})

    def total(tag, field):
        return sum(int(p[tag][field] or 0) for p in pairs)

    def both(field):
        return {t: total(t, field) for t in ('base', 'candidate')}

    def rows(tag, keep=lambda r: True):
        return [r for p in pairs for r in p[tag]['splits_rows'] if keep(r)]

    def walked(tag, keep):
        picked = rows(tag, lambda r: r['dead_end'] and keep(r))
        return {'children': len(picked), 'walked_back_in': sum(r['back_in'] for r in picked),
                'same_mistake': sum(r['stuck'] for r in picked),
                'pearls_eaten_inside_after': sum(r['grew_inside'] for r in picked),
                'born_inside': sum(bool(r['born_inside']) for r in picked)}

    def growth(tag, keep=lambda r: True):
        picked = rows(tag, keep)
        return {'children': len(picked), 'mean_gain': ratio(sum(r['gain'] for r in picked), len(picked)),
                'died': sum(r['child_died'] is not None for r in picked)}

    def visits(tag):
        picked = rows(tag, lambda r: r['dead_end'])
        again = [r for r in picked if r['earlier_here'] > 0]
        knew = [r for r in picked if r['parent_knew']]
        return {'dead_end_splits': len(picked), 'repeat': len(again),
                'repeat_unpaid': sum(r['stay_pearls'] < PAID for r in again),
                'repeat_paid': sum(r['stay_pearls'] >= PAID for r in again),
                'first_time_unpaid': sum(r['stay_pearls'] < PAID for r in picked if r['earlier_here'] == 0),
                'parent_kept_2': sum(r['kept'] == 2 for r in picked),
                'pearls_eaten_on_those_stays': sum(r['stay_pearls'] for r in picked),
                'parent_had_been_told_this_dead_end': len(knew),
                'parent_had_been_told_unpaid': sum(r['stay_pearls'] < PAID for r in knew)}

    games = len(pairs)
    n_splits, pinged, told = both('splits'), both('splits_with_ping'), both('told')
    ends, ends_with_end = both('end_splits'), both('end_splits_with_end')
    with_end, end_true = both('pings_with_end'), both('pings_end_true')
    fire_share = ratio(pinged['candidate'], n_splits['candidate'])
    reach_share = ratio(told['candidate'], pinged['candidate'])
    true_share = ratio(end_true['candidate'], with_end['candidate'])
    end_share = ratio(ends_with_end['candidate'], ends['candidate'])
    silent = sum(1 for p in pairs if p['silent_ok'])
    base_walk = walked('base', lambda r: True)
    told_walk = walked('candidate', lambda r: r['told'])
    untold_walk = walked('candidate', lambda r: not r['told'])
    base_rate = ratio(base_walk['walked_back_in'], base_walk['children'])
    told_rate = ratio(told_walk['walked_back_in'], told_walk['children'])
    seen = {t: visits(t) for t in ('base', 'candidate')}
    unpaid = {t: ratio(seen[t]['repeat_unpaid'], n_splits[t]) for t in ('base', 'candidate')}
    enough = seen['base']['repeat_unpaid'] >= MIN_ENDS and unpaid['candidate'] is not None
    checks = {
        'fires': fire_share is not None and fire_share >= FIRE_SHARE and total('base', 'split_rays') == 0,
        'reach': reach_share is not None and reach_share >= REACH_SHARE,
        'true': true_share is not None and true_share >= TRUE_SHARE,
        'dead_ends_seen': ends['candidate'] >= MIN_ENDS and end_share is not None and end_share >= END_SHARE,
        'nothing_else_changes': silent == games,
        'behaviour': enough and unpaid['candidate'] < unpaid['base'],
    }
    fires_as_specified = all(checks[k] for k in ('fires', 'reach', 'true', 'nothing_else_changes'))
    target_seen = ends['candidate'] >= MIN_ENDS
    passed = all(checks.values())

    by_map = {}
    for p in pairs:
        row = by_map.setdefault(p['map'], {t: {'games': 0, 'splits': 0, 'split_ping': 0, 'child_told': 0,
                                               'dead_end_splits': 0, 'repeat_unpaid': 0, 'repeat_paid': 0}
                                           for t in ('base', 'candidate')})
        for t in ('base', 'candidate'):
            ends_here = [r for r in p[t]['splits_rows'] if r['dead_end']]
            row[t]['games'] += 1
            row[t]['splits'] += p[t]['splits']
            row[t]['split_ping'] += p[t]['splits_with_ping']
            row[t]['child_told'] += p[t]['told']
            row[t]['dead_end_splits'] += len(ends_here)
            row[t]['repeat_unpaid'] += sum(r['earlier_here'] > 0 and r['stay_pearls'] < PAID for r in ends_here)
            row[t]['repeat_paid'] += sum(r['earlier_here'] > 0 and r['stay_pearls'] >= PAID for r in ends_here)

    spots = [s for r in rows('candidate', lambda r: r['told']) for s in r['spots']]

    def used(refill):
        picked = [s for s in spots if s['refill'] == refill]
        return {'told': len(picked), 'stepped_on': sum(s['stepped'] for s in picked),
                'grew_there': sum(s['grew'] for s in picked)}

    cpu = {t: ratio(total(t, 'points'), total(t, 'turns')) if total(t, 'points') else None
           for t in ('base', 'candidate')}
    failed = [k for k, v in checks.items() if not v]
    note = (
        f"{'PASS' if passed else 'FAIL'} ({'all six checks' if passed else 'failed: ' + ', '.join(failed)}). "
        f"{games} paired games. Our splits: candidate {n_splits['candidate']}, base {n_splits['base']}. Split ping "
        f"on the split turn: candidate {pinged['candidate']} (share {fire_share}); base split-ping rays "
        f"{total('base', 'split_rays')}. A ray hit the child on {told['candidate']} of those (share {reach_share}; "
        f"{total('candidate', 'told_on_split_turn')} on the split turn itself, "
        f"{total('candidate', 'splits_resent')} splits were re-sent); rays that hit another teammate "
        f"{total('candidate', 'rays_hit_other_ally')}. Any split-turn ray (whatever it carries) hit the child on "
        f"{total('base', 'split_turn_any_ray_hit_child')}/{n_splits['base']} base splits and "
        f"{total('candidate', 'split_turn_any_ray_hit_child')}/{n_splits['candidate']} candidate splits. Dead ends "
        f"carried in pings {with_end['candidate']}, true on the real map {end_true['candidate']} (share "
        f"{true_share}), passed on from an earlier ping {total('candidate', 'pings_end_passed_on')}. Dead-end "
        f"splits (real map): candidate {ends['candidate']}, base {ends['base']}; with a dead end in the ping "
        f"{ends_with_end['candidate']} (share {end_share}), child told {total('candidate', 'end_splits_told')}. "
        f"Same game up to the first split ping in {silent}/{games} pairs. Repeats (dead-end split in a dead end we "
        f"already split in) with fewer than {PAID} pearls eaten on that stay: base {seen['base']['repeat_unpaid']} "
        f"(share of our splits {unpaid['base']}), candidate {seen['candidate']['repeat_unpaid']} (share "
        f"{unpaid['candidate']})"
        f"{'' if enough else ' (too few in base to compare: need ' + str(MIN_ENDS) + ')'}; repeats with {PAID} or "
        f"more pearls: base {seen['base']['repeat_paid']}, candidate {seen['candidate']['repeat_paid']}; dead-end "
        f"splits by a dragon that had been told that dead end: "
        f"{seen['candidate']['parent_had_been_told_this_dead_end']} "
        f"({seen['candidate']['parent_had_been_told_unpaid']} unpaid). Children of dead-end splits that walked back "
        f"in within {WATCH} rounds: base {base_walk['walked_back_in']}/{base_walk['children']} (share {base_rate}), "
        f"candidate told {told_walk['walked_back_in']}/{told_walk['children']} (share {told_rate}), candidate not "
        f"told {untold_walk['walked_back_in']}/{untold_walk['children']}; of those, died or split again inside: "
        f"base {base_walk['same_mistake']}, told {told_walk['same_mistake']}, not told "
        f"{untold_walk['same_mistake']}. Pearl spots told to a child: refill "
        f"{used(True)}, pearl on the ground {used(False)}. Child gain in its first {WATCH} rounds: base "
        f"{growth('base')}, candidate told {growth('candidate', lambda r: r['told'])}, candidate not told "
        f"{growth('candidate', lambda r: not r['told'])}. Cost: leader messages {total('base', 'leader')} -> "
        f"{total('candidate', 'leader')}, our deaths {total('base', 'deaths')} -> {total('candidate', 'deaths')}, "
        f"timeouts {total('base', 'tle')} -> {total('candidate', 'tle')}, CPU points per turn {cpu['base']} -> "
        f"{cpu['candidate']} (None = not metered). Per map, candidate (splits / with ping / child told / dead-end "
        f"splits / unpaid repeats, base unpaid repeats in brackets): " +
        '; '.join(f"{m} {r['candidate']['splits']} / {r['candidate']['split_ping']} / {r['candidate']['child_told']}"
                  f" / {r['candidate']['dead_end_splits']} / {r['candidate']['repeat_unpaid']} "
                  f"[{r['base']['repeat_unpaid']}]" for m, r in sorted(by_map.items())) + '.')
    result = {
        'passed': passed,
        'note': note,
        'fires_as_specified': fires_as_specified,
        'target_seen': target_seen,
        'behaviour_shown': checks['behaviour'],
        'checks': checks,
        'thresholds': {'FIRE_SHARE': FIRE_SHARE, 'REACH_SHARE': REACH_SHARE, 'TRUE_SHARE': TRUE_SHARE,
                       'MIN_ENDS': MIN_ENDS, 'END_SHARE': END_SHARE, 'PAID': PAID, 'ROOM_MAX': ROOM_MAX,
                       'RESEND': RESEND, 'WATCH': WATCH, 'STUCK': STUCK},
        'built_as': BUILT_AS,
        'games': games,
        'our_splits': n_splits,
        'splits_with_split_ping': pinged,
        'fire_share': fire_share,
        'splits_child_told': told,
        'splits_child_told_on_split_turn': both('told_on_split_turn'),
        'splits_resent': both('splits_resent'),
        'reach_share': reach_share,
        'split_ping_rays': both('split_rays'),
        'split_ping_rays_hit_child': both('rays_hit_child'),
        'split_ping_rays_hit_other_teammate': both('rays_hit_other_ally'),
        'split_ping_rays_outside_a_split_window': both('stray_split_rays'),
        'pings_with_dead_end': with_end,
        'pings_dead_end_true': end_true,
        'true_share': true_share,
        'dead_end_splits': ends,
        'dead_end_splits_with_dead_end_in_ping': ends_with_end,
        'dead_end_splits_child_told': both('end_splits_told'),
        'dead_end_share': end_share,
        'pairs_same_until_first_split_ping': silent,
        'pings_dead_end_passed_on': both('pings_end_passed_on'),
        'splits_any_split_turn_ray_hit_child': both('split_turn_any_ray_hit_child'),
        'dead_end_visits': seen,
        'by_map': by_map,
        'unpaid_repeat_share_of_our_splits': unpaid,
        'enough_unpaid_repeats_in_base': enough,
        'walk_back_in': {'base': base_walk, 'candidate_told': told_walk, 'candidate_not_told': untold_walk,
                         'base_share': base_rate, 'candidate_told_share': told_rate},
        'pearl_spots_in_pings': both('pings_spots'),
        'pearl_spots_in_pings_refill': both('pings_spots_refill'),
        'pearl_spots_told_to_child': {'refill': used(True), 'pearl_on_ground': used(False)},
        'child_first_rounds': {'base': growth('base'), 'candidate_told': growth('candidate', lambda r: r['told']),
                               'candidate_not_told': growth('candidate', lambda r: not r['told'])},
        'our_deaths': both('deaths'),
        'sonar_messages': both('sonar'),
        'leader_messages': both('leader'),
        'mouth_messages': both('mouth'),
        'queen_pings': both('queen'),
        'other_messages': both('other'),
        'unreadable_own_sonar': both('unreadable'),
        'timeouts': both('tle'),
        'cpu_points_per_turn': cpu,
        'cpu_points_max': {t: max((p[t]['points_max'] for p in pairs), default=0) for t in ('base', 'candidate')},
        'limits': 'The dead end is rebuilt from the real map with the bot\'s rule; what a dragon actually knew or '
                  'decided is not in the replay, only where it went. "Told" is the replay\'s record of which dragon '
                  'a ray hit. Pearls on the ground are not read from the replay, only growth, so "unpaid" is what a '
                  'dragon ate on that stay, not what lay there. A lower unpaid-repeat share does not say the game '
                  'went better: a dragon kept out of a dead end also misses the pearls in it, which is why paid '
                  'repeats are shown next to it. Pairs stop being the same game after the first ping, so the two '
                  'columns are totals over different games, not turn-by-turn pairs. Base has no told spots, so spot '
                  'use has no base number. Small counts say little.',
        'pairs': pairs,
    }
    with open(a.output, 'w') as f:
        json.dump(result, f, indent=1)
        f.write('\n')
    print(note)


if __name__ == '__main__':
    main()
