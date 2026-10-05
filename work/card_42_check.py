#!/usr/bin/env python3
"""Card #42 mechanism check (SN_TAIL_MOUTH): a dragon whose tail tip is on a portal opening sends the "this tile is
taken" ping for its tail tile, the same message a head on a portal opening sends today.

usage: python3 work/card_42_check.py --replays DIR --base base --candidate candidate --output FILE
Reads paired replays DIR/<tag>_<map>_<seed>_<side>.replay (side 0 = we are team A).

Words:
  portal opening   a side of a tile that is a portal. Every portal has two.
  far opening      for a tail tile T and one of its portal sides: the tile a dragon stands on when one step through
                   that portal would land it on T.
  chance           one of our dragons ends its turn (it moved or split) with its tail tip on a tile that has a
                   portal side a teammate could come through: the far opening is not the dragon's own second-last
                   body tile. (When it is, the body is still passing through that portal and nobody can stand
                   there; the build sends nothing. Those turns are counted apart as "own body in the portal".)
                   "Knows its tail" = it has lived long enough to have walked its whole body (the bot only
                   remembers tiles its head has been on); only those chances are expected to fire.
  tail warning     our sonar message of the head-on-portal kind ("mouth": tile + round) carrying the sender's real
                   tail tile and the current round, read with our codec key. The head's own ping carries the head.
  wrong tile       a mouth message carrying this round but neither the sender's head nor its tail tile.
  from the tail    the replay gives every sonar ray its start tile: the copy sent into the dragon's own neck starts
                   at the tail tip. Its direction is the one the replay records for that ray.
  straight behind  the direction from the second-last body tile to the tail tip, continued.
  door case        a chance where another dragon of ours has its head on the far opening when the sender's turn
                   ends: the dragon the warning is for. "Warned" = a tail warning for that tile hit that dragon
                   (the replay records which dragon a ray hits) and is still in force on its next turn. That next
                   turn is then followed: went through onto the tail tile, died doing so, or stayed out; and
                   whether the tail tile was still taken at that time.
  tail landing death  one of our dragons dies hitting a body, on a step through a portal, on the tile where a
                   teammate's tail tip is. Counted in both builds, with landings on any other part of a teammate.

Expectation, written before any switch-on game was seen (thresholds are the constants below):
  1. chances: the candidate games hold at least MIN_CHANCES chances by dragons that know their tail, and at least
     GAME_SHARE of the games have one.
  2. fires: at least FIRE_SHARE of those chances carry a tail warning; the base build sends none.
  3. spread: at least FIRE_SHARE of the turns with a tail warning send it in every direction the head's own portal
     ping does not use (3 or 4 rays).
  4. from the tail: at least FIRE_SHARE of the turns with a tail warning have one copy that starts at the tail tip.
  5. right tile: wrong-tile messages are at most WRONG_SHARE of the tail warnings sent.
  6. nothing else changes: every pair plays the same game up to the round of the candidate's first tail warning.
  7. reach: at least MIN_DOOR door cases are seen, and at least REACH_SHARE of them are warned.
passed = all seven. 1-6 say "the ping is sent as the card asks" (fires_as_specified); 7 says "it gets to the dragon
it is for" (target_seen = enough door cases, reach_shown = enough of them warned).
Reported, not part of the verdict: where the tail ray goes (straight behind or not, through the portal or not),
what the door dragons did next, tail landing deaths, and what the warning displaces (leader messages, queen pings,
portal crossings, deaths, timeouts, CPU).
"""
import argparse, concurrent.futures as cf, glob, hashlib, json, os, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

MIN_CHANCES = 200
GAME_SHARE = 0.75
FIRE_SHARE = 0.9
WRONG_SHARE = 0.05
MIN_DOOR = 20
REACH_SHARE = 0.5
LOG_MAX = 40
DIRS = 'NESW'
STEP = {'N': (0, -1), 'E': (1, 0), 'S': (0, 1), 'W': (-1, 0)}
BACK = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}
REASONS = ['wall', 'self', 'body', 'head-on', 'no action']
BUILT_AS = (
    "How Zhe's answer was built. Whenever a dragon's tail tip, as it will be after this turn's move or split, is on "
    "a tile with a portal side, it sends tail tile + round in all four directions; hearers treat it exactly like "
    "the head ping (no change on the hearing side: stay out of a portal landing on that tile for that round and "
    "the next). Sonar can only be sent from the head, so 'from the tail' is the one copy sent into the dragon's own "
    "neck, which the engine lets out at the tail tip; the other three leave from the head. Our choices, not asked "
    "by Zhe: (a) the head's own portal ping keeps its direction when head and tail are both on an opening, unless "
    "that ray would land on our own neck; (b) a dragon that does not know its whole body yet (just split off, or "
    "the first turns of the game) sends nothing; (c) a dragon that makes no action this turn (it dies) sends "
    "nothing; (d) nothing is sent when the tail's only portal side leads straight onto the dragon's own next body "
    "tile (its body is still passing through, no teammate can stand at that opening). While the warning is sent, that round's usual messages (leader position, queen ping) are not.")

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


def unseal(key, wire, streams):
    """Plain message, or None when the keyed check fails."""
    check = (wire & CHECK_MASK) >> 55
    if check not in streams:
        streams[check] = prf(key, CHECK_MASK | check) & CIPHER_MASK
    plain = (wire & (M64 & ~CHECK_MASK)) ^ streams[check]
    return plain if (prf(key, plain & (M64 & ~CHECK_MASK)) & 0xFF) == check else None


def parse(plain):
    """('mouth', tile index, round) for the head-on-portal kind; else the kind only."""
    body = plain & ((1 << 55) - 1)
    if plain >> 63 == 0:
        return ('leader', None, None)
    if (body >> 38) & 0x7FFF == MOUTH_KIND and (body >> 23) & 0x7FFF == 0:
        return ('mouth', body & 0x3FFF, (body >> 14) & 0x1FF)
    if (body >> 42) & 0x7FF == PING_KIND:
        return ('queen', None, None)
    return ('other', None, None)


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


def scan(path, ours):
    """One pass over a replay for our side."""
    root = replay.load(path).root()
    W, H, bodies, team_of, kinds, partner = read_map(root.text(0))
    board = Board(W, H, kinds, partner)
    tag = team_tag(ours)
    key, streams, opened = make_key(W, H, tag), {}, {}

    def index(cell):
        return cell[1] * W + cell[0]

    stat = {k: 0 for k in (
        'sonar', 'unreadable', 'leader', 'queen', 'other', 'head_pings', 'tail_warnings', 'wrong_tile',
        'turns', 'actions', 'points', 'points_max', 'tle', 'crossings', 'deaths',
        'chances', 'chances_known', 'chances_unknown', 'fired_known', 'fired_unknown', 'warn_turns',
        'warn_turns_no_portal', 'warn_full', 'warn_from_tail', 'warn_rays', 'warn_rays_hit_ally',
        'warn_tail_ray_through_portal', 'warn_tail_ray_hit_ally',
        'chances_behind', 'chances_beside', 'span_only', 'span_only_fired',
        'tail_rays', 'tail_rays_straight', 'tail_rays_judged',
        'door', 'door_known', 'door_warned', 'door_behind',
        'portal_tail_deaths', 'portal_ally_deaths', 'portal_other_deaths', 'bad_steps')}
    trail = {i: 1 for i in bodies}
    digests, h = {}, hashlib.sha1()
    pending, heard, door_log, warn_log, death_log, miss_log = {}, {}, [], [], [], []
    first_warning = None
    rnd = 0
    cur = None

    def taken(cell, skip=None):
        """(dragon id, part) on this tile, or None."""
        for i, b in bodies.items():
            if i != skip and cell in b:
                k = list(b).index(cell)
                return i, 'head' if k == 0 else 'tail' if k == len(b) - 1 else 'body'
        return None

    def close_turn():
        nonlocal cur, first_warning
        if cur is None:
            return
        t, cur = cur, None
        did = t['id']
        # What the dragons waiting at a far opening did on this, their next, turn.
        for case in pending.pop(did, []):
            landed = [s for s in t['path'] if s['portal'] and s['to'] == case['tail']]
            fatal = t['fatal']
            case['next'] = ('died on the tail tile' if fatal and fatal['portal'] and fatal['to'] == case['tail']
                            else 'went through' if landed
                            else 'died elsewhere' if did not in bodies else 'stayed out')
            case['tail_tile_still_taken'] = t['blocked'].get(case['tail'])
        for p in t['pings']:
            stat['sonar'] += 1
            if p['kind'] != 'mouth':
                stat[p['kind']] += 1
        if did not in bodies or len(bodies[did]) < 2:
            return
        body = bodies[did]
        head, tail, prev = body[0], body[-1], body[-2]
        mouths = [p for p in t['pings'] if p['kind'] == 'mouth' and p['when'] == (rnd & 0x1FF)]
        warns = [p for p in mouths if p['cell'] == index(tail)]
        heads = [p for p in mouths if p['cell'] == index(head)]
        stat['head_pings'] += len(heads)
        stat['tail_warnings'] += len(warns)
        stat['wrong_tile'] += len(mouths) - len(warns) - len(heads)
        sides = [ch for ch in DIRS if board.side(tail, ch) == 2]
        open_sides = [ch for ch in sides if board.through(tail, ch) != prev]
        back = next((ch for ch in DIRS if board.side(prev, ch) == 0 and board.beside(prev, ch) == tail), None)
        tail_rays = [p for p in t['pings'] if p['origin'] == tail]
        for p in tail_rays:
            stat['tail_rays'] += 1
            if back is not None:
                stat['tail_rays_judged'] += 1
                stat['tail_rays_straight'] += p['dir'] == back
        acted = bool(t['path']) or t['split']
        if warns:
            stat['warn_turns'] += 1
            stat['warn_turns_no_portal'] += not sides
            stat['warn_full'] += len(warns) + len(heads) >= 4 and len(warns) >= 3
            stat['warn_rays'] += len(warns)
            stat['warn_rays_hit_ally'] += sum(1 for p in warns if p['hit'] is not None and team_of.get(p['hit']) == ours)
            from_tail = [p for p in warns if p['origin'] == tail]
            stat['warn_from_tail'] += bool(from_tail)
            stat['warn_tail_ray_through_portal'] += any(board.side(tail, p['dir']) == 2 for p in from_tail)
            stat['warn_tail_ray_hit_ally'] += any(p['hit'] is not None and team_of.get(p['hit']) == ours
                                                  for p in from_tail)
            for p in warns:
                if p['hit'] is not None:
                    heard[(p['hit'], tail)] = rnd
            if first_warning is None:
                first_warning = rnd
            if len(warn_log) < LOG_MAX:
                warn_log.append({'round': rnd, 'id': did, 'length': len(body), 'head': head, 'tail': tail,
                                 'portal_sides': sides, 'straight_behind': back,
                                 'rays': [{'dir': p['dir'], 'from': 'tail' if p['origin'] == tail else 'head',
                                           'end': p['end'], 'hit': p['hit']} for p in warns],
                                 'head_ping_rays': len(heads)})
        if not sides or not acted:
            return
        if not open_sides:
            stat['span_only'] += 1
            stat['span_only_fired'] += bool(warns)
            return
        stat['chances'] += 1
        known = t['known']
        stat['chances_known' if known else 'chances_unknown'] += 1
        stat['fired_known' if known else 'fired_unknown'] += bool(warns)
        stat['chances_behind' if back in open_sides else 'chances_beside'] += 1
        if known and not warns and len(miss_log) < LOG_MAX:
            miss_log.append({'round': rnd, 'id': did, 'length': len(body), 'head': head, 'tail': tail,
                             'steps': len(t['path']), 'split': t['split'], 'mouth_messages': len(mouths)})
        seen = set()
        for ch in open_sides:
            far = board.through(tail, ch)
            if far is None or board.through(far, BACK[ch]) != tail:
                continue
            for other, b in bodies.items():
                if other == did or team_of.get(other) != ours or b[0] != far or (other, far) in seen:
                    continue
                seen.add((other, far))
                # A warning holds for the round it was sent and the next; one from last round is still good on
                # the waiting dragon's next turn only when that turn comes later this round.
                last = heard.get((other, tail))
                warned = last == rnd or (last == rnd - 1 and other > did)
                case = {'round': rnd, 'sender': did, 'tail': tail, 'far_opening': far, 'waiting': other,
                        'sender_knows_tail': known, 'warning_sent': bool(warns), 'warned': warned,
                        'portal_straight_behind': ch == back, 'waiting_moves_first_next_round': other < did,
                        'next': 'game ended', 'tail_tile_still_taken': None}
                stat['door'] += 1
                stat['door_known'] += known
                stat['door_warned'] += warned
                stat['door_behind'] += ch == back
                pending.setdefault(other, []).append(case)
                door_log.append(case)

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
            stat['actions'] += 1
            stat['points'] += points
            stat['points_max'] = max(stat['points_max'], points)
            stat['tle'] += pl.bit(32)
            action = pl.pointer(0)
            steps = []
            if action is not None and action.u16(0) == 0 and action.pointer(0) is not None:
                steps = [DIRS[v] for v in action.pointer(0) if v < 4]
            trail[did] = min(trail.get(did, 1), len(bodies[did]))
            cur = {'id': did, 'known': trail[did] == len(bodies[did]), 'steps': steps, 'path': [], 'split': False,
                   'pings': [], 'fatal': None,
                   'blocked': {case['tail']: taken(case['tail']) is not None for case in pending.get(did, [])}}
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            head, tail = replay.point(pl.pointer(0)), replay.point(pl.pointer(1))
            h.update(f'u{did}{head}{tail}'.encode())
            body = bodies.setdefault(did, deque())
            if body and body[0] != head:
                left = body[0]
                ways = [ch for ch in DIRS if board.through(left, ch) == head]
                mine = cur is not None and cur['id'] == did
                want = cur['steps'][len(cur['path'])] if mine and len(cur['path']) < len(cur['steps']) else None
                ch = want if want in ways else next((c for c in ways if board.side(left, c) != 2), ways[0] if ways else None)
                if ch is None:
                    stat['bad_steps'] += 1
                portal = ch is not None and board.side(left, ch) == 2
                if team_of.get(did) == ours:
                    stat['crossings'] += portal
                    trail[did] = trail.get(did, 1) + 1
                if mine:
                    cur['path'].append({'from': left, 'to': head, 'portal': portal})
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
            trail[child] = 1
            if cur is not None and cur['id'] == parent:
                cur['split'] = True
        elif kind == 'dragonDeath':
            did, reason = pl.i32(0), pl.u16(4)
            h.update(f'd{did}{reason}'.encode())
            if team_of.get(did) == ours:
                stat['deaths'] += 1
                if (cur is not None and cur['id'] == did and did in bodies and reason == 2 and
                        len(cur['path']) < len(cur['steps'])):
                    ch = cur['steps'][len(cur['path'])]
                    left = bodies[did][0]
                    to = board.through(left, ch)
                    portal = board.side(left, ch) == 2
                    owner = taken(to, skip=did) if to is not None else None
                    cur['fatal'] = {'to': to, 'portal': portal}
                    if portal:
                        ally = owner is not None and team_of.get(owner[0]) == ours
                        field = ('portal_tail_deaths' if ally and owner[1] == 'tail' else
                                 'portal_ally_deaths' if ally else 'portal_other_deaths')
                        stat[field] += 1
                        if len(death_log) < LOG_MAX:
                            death_log.append({'round': rnd, 'id': did, 'from': left, 'onto': to,
                                              'hit_dragon': owner[0] if owner else None,
                                              'hit_part': owner[1] if owner else None, 'teammate': ally})
            bodies.pop(did, None)
        elif kind == 'sonarPing':
            if cur is None or pl.i32(0) != cur['id']:
                continue
            wire = pl.u64(16)
            if ((wire & TAG_MASK) >> 53) != tag:
                continue
            if wire not in opened:
                plain = unseal(key, wire, streams)
                opened[wire] = parse(plain) if plain is not None else ('unreadable', None, None)
            what, cell, when = opened[wire]
            cur['pings'].append({'kind': what, 'cell': cell, 'when': when, 'dir': DIRS[pl.u16(4) % 4],
                                 'origin': replay.point(pl.pointer(0)), 'end': replay.point(pl.pointer(1)),
                                 'hit': pl.i32(12) if pl.u16(6) else None})
    close_turn()
    digests[rnd] = h.hexdigest()
    if stat['bad_steps']:
        raise ValueError(f"{path}: {stat['bad_steps']} head steps fit no open side or portal; map sides misread")
    return {'digests': digests, 'first_warning_round': first_warning, 'rounds': rnd, **stat,
            'door_log': door_log, 'warn_log': warn_log, 'death_log': death_log, 'miss_log': miss_log}


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
    for n, k in enumerate(keys):
        b, c = scans[2 * n], scans[2 * n + 1]
        diff = first_diff(b.pop('digests'), c.pop('digests'))
        pairs.append({'map': k[0], 'seed': k[1], 'side': k[2], 'first_diff_round': diff,
                      'silent_ok': diff is None or (c['first_warning_round'] is not None and
                                                    diff >= c['first_warning_round']),
                      'base': b, 'candidate': c})

    def total(tag, field):
        return sum(int(p[tag][field] or 0) for p in pairs)

    def both(field):
        return {t: total(t, field) for t in ('base', 'candidate')}

    games = len(pairs)
    chances = both('chances_known')
    fired = both('fired_known')
    warn_turns = both('warn_turns')
    warnings = both('tail_warnings')
    wrong = both('wrong_tile')
    door = both('door')
    warned = both('door_warned')
    games_with = sum(1 for p in pairs if p['candidate']['chances_known'] > 0)
    fire_share = ratio(fired['candidate'], chances['candidate'])
    full_share = ratio(total('candidate', 'warn_full'), warn_turns['candidate'])
    tail_share = ratio(total('candidate', 'warn_from_tail'), warn_turns['candidate'])
    wrong_share = ratio(wrong['candidate'], warnings['candidate'])
    reach_share = ratio(warned['candidate'], door['candidate'])
    silent = sum(1 for p in pairs if p['silent_ok'])
    checks = {
        'chances': chances['candidate'] >= MIN_CHANCES and games_with >= GAME_SHARE * games,
        'fires': fire_share is not None and fire_share >= FIRE_SHARE and warnings['base'] == 0,
        'spread': full_share is not None and full_share >= FIRE_SHARE,
        'from_tail': tail_share is not None and tail_share >= FIRE_SHARE,
        'right_tile': wrong_share is not None and wrong_share <= WRONG_SHARE,
        'nothing_else_changes': silent == games,
        'reach': door['candidate'] >= MIN_DOOR and reach_share is not None and reach_share >= REACH_SHARE,
    }
    fires_as_specified = all(v for k, v in checks.items() if k != 'reach')
    target_seen = door['candidate'] >= MIN_DOOR
    passed = all(checks.values())

    def nexts(tag, only=None):
        out = {}
        for p in pairs:
            for case in p[tag]['door_log']:
                if only is None or case['warned'] == only:
                    label = case['next']
                    if case['next'] == 'stayed out' and case['tail_tile_still_taken'] is False:
                        label = 'stayed out, tile already free'
                    out[label] = out.get(label, 0) + 1
        return out

    rays = both('tail_rays_judged')
    straight = both('tail_rays_straight')
    behind = both('chances_behind')
    all_chances = both('chances')
    through = total('candidate', 'warn_tail_ray_through_portal')
    deaths_tail = both('portal_tail_deaths')
    # No recorded points means the games ran without CPU metering.
    cpu = {t: ratio(total(t, 'points'), total(t, 'actions')) if total(t, 'points') else None
           for t in ('base', 'candidate')}
    failed = [k for k, v in checks.items() if not v]
    note = (
        f"{'PASS' if passed else 'FAIL'} ({'all seven checks' if passed else 'failed: ' + ', '.join(failed)}). "
        f"{games} paired games. Chances (tail tip on a portal opening, dragon knows its tail): candidate "
        f"{chances['candidate']} in {games_with}/{games} games, base {chances['base']}. Tail warning sent on "
        f"{fired['candidate']} of them (share {fire_share}); base sent {warnings['base']}. Of the "
        f"{warn_turns['candidate']} turns with a warning, share {full_share} used every free direction and share "
        f"{tail_share} had a copy start at the tail tip; wrong-tile messages {wrong['candidate']} of "
        f"{warnings['candidate']} warnings (base {wrong['base']}). Same game up to the first warning in "
        f"{silent}/{games} pairs. Where the tail copy goes: in both builds a ray sent into the dragon's own body "
        f"left straight behind the tail on {straight['base'] + straight['candidate']} of "
        f"{rays['base'] + rays['candidate']} rays; the portal was straight behind the tail on "
        f"{behind['candidate']} of {all_chances['candidate']} candidate chances, and the tail copy went through "
        f"the portal on {through} warning turns. Door cases (a teammate's head on the far opening): candidate "
        f"{door['candidate']}, base {door['base']}; portal straight behind the tail in "
        f"{total('candidate', 'door_behind')} of the candidate's; warned {warned['candidate']} (share "
        f"{reach_share}); what they "
        f"did next, candidate {nexts('candidate')}, base {nexts('base')}. Tail landing deaths (through a portal "
        f"onto a teammate's tail tip): base {deaths_tail['base']}, candidate {deaths_tail['candidate']}. Cost: "
        f"leader messages {total('base', 'leader')} -> {total('candidate', 'leader')}, queen pings "
        f"{total('base', 'queen')} -> {total('candidate', 'queen')}, our portal crossings "
        f"{total('base', 'crossings')} -> {total('candidate', 'crossings')}, our deaths {total('base', 'deaths')} "
        f"-> {total('candidate', 'deaths')}, timeouts {total('base', 'tle')} -> {total('candidate', 'tle')}, "
        f"CPU points per action {cpu['base']} -> {cpu['candidate']} (None = not metered).")
    result = {
        'passed': passed,
        'note': note,
        'fires_as_specified': fires_as_specified,
        'target_seen': target_seen,
        'reach_shown': checks['reach'],
        'checks': checks,
        'thresholds': {'MIN_CHANCES': MIN_CHANCES, 'GAME_SHARE': GAME_SHARE, 'FIRE_SHARE': FIRE_SHARE,
                       'WRONG_SHARE': WRONG_SHARE, 'MIN_DOOR': MIN_DOOR, 'REACH_SHARE': REACH_SHARE},
        'built_as': BUILT_AS,
        'games': games,
        'games_with_a_chance': games_with,
        'chances_all': all_chances,
        'chances_tail_known': chances,
        'chances_tail_not_known': both('chances_unknown'),
        'fired_tail_known': fired,
        'fired_tail_not_known': both('fired_unknown'),
        'fire_share': fire_share,
        'turns_with_warning': warn_turns,
        'turns_with_warning_tail_not_on_portal': both('warn_turns_no_portal'),
        'turns_with_warning_every_free_direction': both('warn_full'),
        'every_free_direction_share': full_share,
        'turns_with_warning_copy_from_tail': both('warn_from_tail'),
        'copy_from_tail_share': tail_share,
        'tail_warning_rays': warnings,
        'tail_warning_rays_hit_a_teammate': both('warn_rays_hit_ally'),
        'wrong_tile_messages': wrong,
        'wrong_tile_share': wrong_share,
        'head_ping_rays': both('head_pings'),
        'pairs_same_until_first_warning': silent,
        'tail_ray_direction': {'rays_with_a_plain_last_segment': rays, 'left_straight_behind': straight,
                               'all_rays_from_tail': both('tail_rays')},
        'chances_portal_straight_behind_tail': behind,
        'chances_portal_beside_tail': both('chances_beside'),
        'turns_own_body_in_the_portal': both('span_only'),
        'turns_own_body_in_the_portal_with_warning': both('span_only_fired'),
        'warning_turns_tail_copy_through_portal': both('warn_tail_ray_through_portal'),
        'warning_turns_tail_copy_hit_a_teammate': both('warn_tail_ray_hit_ally'),
        'door_cases': door,
        'door_cases_sender_knows_tail': both('door_known'),
        'door_cases_portal_straight_behind': both('door_behind'),
        'door_cases_warned': warned,
        'reach_share': reach_share,
        'door_next_turn': {t: nexts(t) for t in ('base', 'candidate')},
        'door_next_turn_warned': nexts('candidate', True),
        'door_next_turn_not_warned': nexts('candidate', False),
        'portal_tail_landing_deaths': deaths_tail,
        'portal_landing_deaths_other_teammate_part': both('portal_ally_deaths'),
        'portal_landing_deaths_other': both('portal_other_deaths'),
        'our_deaths': both('deaths'),
        'our_portal_crossings': both('crossings'),
        'sonar_messages': both('sonar'),
        'leader_messages': both('leader'),
        'queen_pings': both('queen'),
        'other_messages': both('other'),
        'unreadable_own_sonar': both('unreadable'),
        'timeouts': both('tle'),
        'cpu_points_per_action': cpu,
        'cpu_points_max': {t: max((p[t]['points_max'] for p in pairs), default=0) for t in ('base', 'candidate')},
        'limits': 'Whether a dragon knows its tail is rebuilt from the replay (tiles its head has walked), not read '
                  'from the bot. "Warned" is the replay\'s record of which dragon a ray hit; what the hearer then '
                  'decided is only seen as where it went. A door dragon that stayed out may never have meant to '
                  'go through. Tail landing deaths and door cases are rare events: small counts say little.',
        'pairs': pairs,
    }
    with open(a.output, 'w') as f:
        json.dump(result, f, indent=1)
        f.write('\n')
    print(note)


if __name__ == '__main__':
    main()
