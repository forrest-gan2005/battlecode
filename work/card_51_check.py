#!/usr/bin/env python3
"""Card #51 stall-release mechanism check (TR_STALL_RELEASE): do our short dragons leave a walled start room once
the centre pull has stopped moving them?

usage: python3 work/card_51_check.py --replays DIR --base base --candidate candidate --output FILE
Reads paired replays DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1; side 0 = we are team A).

Words (all read from the map inside the replay, no map names):
  centre rule    the opening rule that pulls a dragon of length 4 or less toward the middle of the map. It is on for
                 maps of 1000 tiles or fewer that are at least twice as wide as tall (rounds 0-59), and for maps of
                 700 tiles or fewer (rounds 0-29). Same test as the bot's.
  room           tiles that lie in a fully open 2x2 square, joined when they share such a square. A passage one
                 tile wide is never part of a room, so a room ends at its one-tile exits.
  home           the rooms our starting dragons stand in.
  walled start   every starting dragon of ours is in a room, the home is at most a quarter of the map, the middle
                 of the map is not in it, and the home tile nearest the middle has no open side toward a tile that
                 is nearer still (the straight line to the middle ends at a wall: the way out leads away).
  pin zone       home tiles within 2 steps of the home's nearest distance to the middle.
  outside        a head of ours on a tile that is not in the home.
  stalled        rebuilt from the replay exactly as the bot keeps it: each dragon remembers the round it last
                 started a turn nearer to the middle (straight line, walls ignored) than ever before; stalled =
                 the centre rule is on for it (round and length) and that round is 12 or more rounds ago. In the
                 candidate these are the turns the switch acts on; in base they are the turns it would act on.
  door chance    one of our dragons starts its turn on a home tile that has an open side to a free tile outside
                 the home. "Taken" = its first step that turn goes outside.
  pearls         length gained by our dragons by moving (a pearl eaten).

Expectation, written before any switch-on game was played (thresholds are the constants below). Walled-start
games are judged layout by layout (one map = one layout; a layout needs MIN_LAYOUT paired games):
  1. target seen: on at least one walled-start layout base shows the card's problem: the stall test comes true
     inside the home in at least TARGET_SHARE of its games, and base's median first round with a head outside is
     after round EXIT_MAX or never. Layouts where base does not show it are reported and do not count.
  2. fires: on every layout with the problem, the candidate's stall test comes true inside the home in every game.
  3. nothing else changes: every pair, on every map, plays the same game up to the round of the candidate's first
     stalled turn.
  4. leaves: on every layout with the problem, the candidate's median first round with a head outside is EXIT_MAX
     or earlier (the card: still after round 45 = another rule holds them), and base's is at least EXIT_GAIN rounds
     later or never.
  5. stays out: on every layout with the problem, at least OUT_SHARE of the candidate's turns in rounds 30-59 start
     outside (the card: at least 30%, 0% now).
  6. pearls: on every layout with the problem, the candidate's median pearls by round 100 is above PEARL_WRONG (the
     card: 7 or fewer = leaving is not the bottleneck).
passed = all six.
The card also names round 30 as the expected median first exit. That is reported, not gated: the stall clock is 12
rounds after the last new nearest mark and the pin corner of a 7x7 room is 13 steps from the first tile outside, so
on the ladder layout round 30 is about the earliest exit the rule allows at all.
Reported, not part of the verdict: the card's own targets (first exit by round EXIT_TARGET, PEARL_TARGET pearls by
round 100), what happens at the door, time in the pin zone, tiles visited, dragons alive at round 100, wins, and on
every map our wall / own-body deaths and queen deaths in rounds 0-100 (the card: a rise on corridor layouts would
show the no-tail waiver sends short dragons into dead ends), how often the stall test is true, timeouts and CPU.
"""
import argparse, concurrent.futures as cf, glob, hashlib, json, os, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# PASS RULE (fixed before any switch-on game was played)
MIN_LAYOUT = 4       # paired walled-start games a layout needs to be judged (two seeds, both sides)
TARGET_SHARE = 0.75  # share of a layout's base games where the stall test must come true inside the home
EXIT_MAX = 45        # base's median first exit must be later (or never); the candidate's this or earlier
EXIT_GAIN = 15       # and base's median this many rounds later than the candidate's (or never)
OUT_SHARE = 0.30     # candidate turns in rounds 30-59 that start outside the home
PEARL_WRONG = 7      # candidate's median pearls by round 100 must be above this
# The card's own targets, reported only.
EXIT_TARGET = 30
PEARL_TARGET = 15

# The bot's settings this check mirrors (mybot2/main.cpp).
STALL_ROUNDS = 12            # TR_STALL_ROUNDS
CENTER_MAX_LENGTH = 4
CENTER_MAX_CELLS = 1000
CENTER_SMALL_CELLS = 700
CENTER_ROUNDS = 60
CENTER_SMALL_ROUNDS = 30

ROOM_SHARE = 0.25    # a home larger than this share of the map is not a walled start
PIN_SLACK = 2
DOOR_ROUNDS = 120    # door chances are counted in rounds 0-119
DEATH_ROUNDS = 100
REASONS = ['wall', 'self', 'body', 'head-on', 'no action']
BUILT_AS = (
    "How the card was built. Each dragon keeps two numbers: its nearest-ever straight-line distance to the middle "
    "of the map at the start of a turn, and the round it set that. While the centre rule is on for it (map, round "
    "limit, length 4 or less) and that round is 12 or more rounds ago, (a) the centre pull is skipped for it and "
    "(b) the 600 no-tail charge is skipped for a step whose room ahead (free tiles, unseen ones counting half, "
    "minus what nearby allies need) is at least 6 x length + 8. Defaults from the questions step, nobody "
    "overruled them: a dragon that sets a new nearest mark gets the pull back for another 12 rounds; the waiver "
    "stops when the centre rule stops (round 30 or 60, or length 5); the queen is released like any other dragon "
    "and keeps her own dead-end and room penalties; a dragon born from a split starts its clock on its first turn; "
    "the clock runs on turns when a pearl is in range.")


def gap(a, b, size):
    raw = abs(a - b)
    return min(raw, size - raw)


class Board:
    """Walls, rooms and start dragons of the map text inside a replay."""

    def __init__(self, text):
        W = H = 0
        E = {}
        self.bodies, self.team_of = {}, {}
        for line in text.splitlines():
            q = line.split()
            if not q:
                continue
            if q[0] == 'MAP':
                W, H = int(q[1]), int(q[2])
            elif q[0] == 'EDGE':
                E[int(q[1])] = max(E.get(int(q[1]), 0), int(q[2]))
            elif q[0] == 'DRAGON':
                did = len(self.bodies)
                self.bodies[did] = [int(q[4 + 2 * k]) * W + int(q[3 + 2 * k]) for k in range(int(q[2]))]
                self.team_of[did] = 'A' if int(q[1]) == 0 else 'B'
        if not W or not H:
            raise ValueError('replay carries no map size')
        self.W, self.H = W, H
        # Side ids run in rows of W + 1: a row of north sides, then a row of west sides. Generated maps also carry
        # the wrap-around copies (bottom row, right column); official maps leave those ids out.
        R = W + 1

        def kind(ids):
            return max(E.get(i, 0) for i in ids)

        def north(x, y):
            return kind([2 * y * R + x] + ([2 * H * R + x] if y == 0 else []))

        def west(x, y):
            return kind([(2 * y + 1) * R + x] + ([(2 * y + 1) * R + W] if x == 0 else []))

        # Per tile, in N E S W order: neighbour and side kind (0 open, 1 kelp, 2 portal).
        self.nb, self.side = [], []
        for y in range(H):
            for x in range(W):
                self.nb.append((((y - 1) % H) * W + x, y * W + (x + 1) % W, ((y + 1) % H) * W + x, y * W + (x - 1) % W))
                self.side.append((north(x, y), west((x + 1) % W, y), north(x, (y + 1) % H), west(x, y)))
        cells = W * H
        long_map = W >= 2 * H
        self.center_map = cells <= CENTER_MAX_CELLS and (long_map or cells <= CENTER_SMALL_CELLS)
        self.center_rounds = CENTER_ROUNDS if long_map else CENTER_SMALL_ROUNDS
        self.centre = (H // 2) * W + W // 2
        self.dist = [gap(c % W, W // 2, W) + gap(c // W, H // 2, H) for c in range(cells)]

        # Rooms: union the four tiles of every fully open 2x2 square.
        parent = list(range(cells))

        def find(c):
            while parent[c] != c:
                parent[c] = parent[parent[c]]
                c = parent[c]
            return c

        floor = bytearray(cells)
        if W >= 2 and H >= 2:
            for c in range(cells):
                e, s = self.nb[c][1], self.nb[c][2]
                d = self.nb[e][2]
                if self.side[c][1] or self.side[c][2] or self.side[e][2] or self.side[s][1] or len({c, e, s, d}) < 4:
                    continue
                for o in (c, e, s, d):
                    floor[o] = 1
                    parent[find(o)] = find(c)
        self.room_of = {c: find(c) for c in range(cells) if floor[c]}
        self.room_tiles = {}
        for c, r in self.room_of.items():
            self.room_tiles.setdefault(r, set()).add(c)

    def pinned(self, room):
        """The room tile nearest the middle has no open side toward a tile that is nearer still."""
        tiles = self.room_tiles[room]
        low = min(self.dist[c] for c in tiles)
        return not any(self.side[c][d] == 0 and self.dist[self.nb[c][d]] < low
                       for c in tiles if self.dist[c] == low for d in range(4))

    def home(self, team):
        rooms, loose = [], 0
        for did, body in self.bodies.items():
            if self.team_of[did] != team:
                continue
            room = self.room_of.get(body[0])
            if room is None:
                loose += 1
            elif room not in rooms:
                rooms.append(room)
        tiles = set().union(*[self.room_tiles[r] for r in rooms]) if rooms else set()
        walled = bool(rooms) and not loose and len(tiles) <= ROOM_SHARE * self.W * self.H and self.centre not in tiles
        pin = set()
        for r in rooms:
            low = min(self.dist[c] for c in self.room_tiles[r])
            pin |= {c for c in self.room_tiles[r] if self.dist[c] <= low + PIN_SLACK}
        doors = {}
        for c in tiles:
            out = [self.nb[c][d] for d in range(4) if self.side[c][d] == 0 and self.nb[c][d] not in tiles]
            if out:
                doors[c] = out
        return {'tiles': tiles, 'rooms': sorted(len(self.room_tiles[r]) for r in rooms), 'loose': loose,
                'walled': walled, 'pinned': walled and all(self.pinned(r) for r in rooms), 'pin': pin, 'doors': doors}


def scan(path, ours):
    """One pass over a replay for our side."""
    root = replay.load(path).root()
    board = Board(root.text(0))
    W = board.W
    home = board.home(ours)
    tiles, pin, doors = home['tiles'], home['pin'], home['doors']
    result = root.pointer(4)
    winner = ('A', 'B')[result.u16(6)] if result.u16(4) == 1 else None
    bodies = {i: deque(b) for i, b in board.bodies.items()}
    team_of = dict(board.team_of)
    queen = next((i for i in (0, 1) if team_of.get(i) == ours), None)

    stat = {k: 0 for k in (
        'turns', 'turns_0_59', 'out_0_59', 'turns_30_59', 'out_30_59', 'rule_turns', 'pin_rule_turns',
        'stalled_turns', 'stalled_home_turns', 'door_stalled', 'door_stalled_taken', 'door_other',
        'door_other_taken', 'pearls_60', 'pearls_100', 'pearls', 'points', 'points_max', 'tle', 'splits_100')}
    deaths = [0] * len(REASONS)
    best = {}
    visited = set()
    first_exit = first_stall = first_stall_home = queen_death = None
    units_100 = None
    digests, h = {}, hashlib.sha1()
    rnd = 0
    cur = None

    def mine(did):
        return team_of.get(did) == ours

    def note_head(did):
        nonlocal first_exit
        if not mine(did) or not bodies.get(did):
            return
        head = bodies[did][0]
        if rnd <= 100:
            visited.add(head)
        if tiles and head not in tiles and first_exit is None:
            first_exit = rnd

    for did in list(bodies):
        note_head(did)

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else '?'
        pl = ev.pointer(0)
        if kind == 'roundStart':
            cur = None
            digests[rnd] = h.hexdigest()
            rnd = pl.i32(0)
            h = hashlib.sha1()
            if rnd == 100:
                units_100 = sum(1 for i, b in bodies.items() if b and mine(i))
        elif kind == 'dragonAction':
            cur = None
            did = pl.i32(0)
            if not mine(did) or not bodies.get(did):
                continue
            usage = pl.pointer(1)
            points = usage.u64(0) if usage else 0
            stat['points'] += points
            stat['points_max'] = max(stat['points_max'], points)
            stat['tle'] += pl.bit(32)
            body = bodies[did]
            head, length = body[0], len(body)
            # The bot's stall clock: nearest-ever distance to the middle at a turn start, and the round it was set.
            mark = best.get(did)
            if mark is None or board.dist[head] < mark[0]:
                mark = best[did] = (board.dist[head], rnd)
            rule = board.center_map and rnd < board.center_rounds and length <= CENTER_MAX_LENGTH
            stalled = rule and rnd - mark[1] >= STALL_ROUNDS
            inside = head in tiles
            stat['turns'] += 1
            stat['rule_turns'] += rule
            stat['pin_rule_turns'] += rule and head in pin
            stat['stalled_turns'] += stalled
            stat['stalled_home_turns'] += stalled and inside
            if stalled and first_stall is None:
                first_stall = rnd
            if stalled and inside and first_stall_home is None:
                first_stall_home = rnd
            if tiles and rnd <= 59:
                stat['turns_0_59'] += 1
                stat['out_0_59'] += not inside
                if rnd >= 30:
                    stat['turns_30_59'] += 1
                    stat['out_30_59'] += not inside
            action = pl.pointer(0)
            moving = action is not None and action.u16(0) == 0
            if action is not None and action.u16(0) == 1 and rnd <= 100:
                stat['splits_100'] += 1
            if moving and rnd < DOOR_ROUNDS and head in doors:
                taken_by = {c for b in bodies.values() for c in b}
                if any(c not in taken_by for c in doors[head]):
                    tag = 'door_stalled' if stalled else 'door_other'
                    stat[tag] += 1
                    cur = {'id': did, 'tag': tag}
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            hx, hy = replay.point(pl.pointer(0))
            tx, ty = replay.point(pl.pointer(1))
            head, tail = hy * W + hx, ty * W + tx
            h.update(f'u{did}{(hx, hy)}{(tx, ty)}'.encode())
            body = bodies.setdefault(did, deque())
            before = len(body)
            if not body or body[0] != head:
                body.appendleft(head)
                if cur is not None and cur['id'] == did:
                    stat[cur['tag'] + '_taken'] += head not in tiles
                    cur = None
            while len(body) > 1 and body[-1] != tail:
                body.pop()
            if mine(did) and before > 0 and len(body) > before:
                stat['pearls'] += 1
                stat['pearls_60'] += rnd <= 60
                stat['pearls_100'] += rnd <= 100
            note_head(did)
        elif kind == 'dragonSplit':
            parent, child = pl.i32(0), pl.i32(4)
            h.update(f's{parent}{child}'.encode())
            team = ('A', 'B')[pl.u16(8)]
            for did, part in ((parent, pl.pointer(0)), (child, pl.pointer(1))):
                bodies[did] = deque(replay.point(p)[1] * W + replay.point(p)[0] for p in part)
                team_of[did] = team
                note_head(did)
        elif kind == 'dragonDeath':
            did, reason = pl.i32(0), pl.u16(4)
            h.update(f'd{did}{reason}'.encode())
            if mine(did):
                if rnd <= DEATH_ROUNDS and reason < len(REASONS):
                    deaths[reason] += 1
                if did == queen and queen_death is None:
                    queen_death = rnd
            bodies.pop(did, None)
    digests[rnd] = h.hexdigest()
    if units_100 is None:
        units_100 = sum(1 for i, b in bodies.items() if b and mine(i))
    return {'digests': digests, 'size': [board.W, board.H], 'center_map': board.center_map,
            'center_rounds': board.center_rounds, 'home_rooms': home['rooms'], 'home_tiles': len(tiles),
            'start_dragons_not_in_a_room': home['loose'], 'walled': home['walled'], 'pinned': home['pinned'],
            'judged': bool(board.center_map and home['walled'] and home['pinned']),
            'rounds': rnd, 'win': int(winner == ours), 'first_exit': first_exit, 'first_stall': first_stall,
            'first_stall_home': first_stall_home, 'tiles_visited_100': len(visited), 'units_100': units_100,
            'deaths_0_100': dict(zip(REASONS, deaths)), 'queen_death_round': queen_death, **stat}


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


def median(values):
    """Median where None means 'never' and sorts last; None when the middle is a never."""
    if not values:
        return None
    rank = sorted(values, key=lambda v: (v is None, v or 0))
    mid = rank[(len(rank) - 1) // 2: len(rank) // 2 + 1]
    return None if any(v is None for v in mid) else sum(mid) / len(mid)


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
        pairs.append({'map': k[0], 'seed': k[1], 'side': k[2], 'judged': b['judged'], 'first_diff_round': diff,
                      'silent_ok': diff is None or (c['first_stall'] is not None and diff >= c['first_stall']),
                      'base': b, 'candidate': c})
    tags = ('base', 'candidate')
    walled = [p for p in pairs if p['judged']]
    other = [p for p in pairs if not p['judged']]

    def total(group, tag, field):
        return sum(int(p[tag][field] or 0) for p in group)

    def both(group, field):
        return {t: total(group, t, field) for t in tags}

    def med(group, field):
        return {t: median([p[t][field] for p in group]) for t in tags}

    def games_with(group, field):
        return {t: sum(1 for p in group if p[t][field] is not None) for t in tags}

    def share(group, top, bottom):
        return {t: ratio(total(group, t, top), total(group, t, bottom)) for t in tags}

    def death_sum(group, reasons):
        return {t: sum(p[t]['deaths_0_100'][r] for p in group for r in reasons) for t in tags}

    def block(group):
        return {
            'games': len(group),
            'wins': both(group, 'win'),
            'first_exit_rounds': {t: [p[t]['first_exit'] for p in group] for t in tags},
            'first_exit_median': med(group, 'first_exit'),
            'games_with_an_exit': games_with(group, 'first_exit'),
            'turns_rounds_30_59': both(group, 'turns_30_59'),
            'turns_outside_rounds_30_59': both(group, 'out_30_59'),
            'outside_share_rounds_30_59': share(group, 'out_30_59', 'turns_30_59'),
            'outside_share_rounds_0_59': share(group, 'out_0_59', 'turns_0_59'),
            'pearls_by_round_60': {t: [p[t]['pearls_60'] for p in group] for t in tags},
            'pearls_by_round_100': {t: [p[t]['pearls_100'] for p in group] for t in tags},
            'pearls_by_round_100_median': med(group, 'pearls_100'),
            'tiles_visited_by_round_100_median': med(group, 'tiles_visited_100'),
            'dragons_alive_round_100': {t: [p[t]['units_100'] for p in group] for t in tags},
            'turns_centre_rule_on': both(group, 'rule_turns'),
            'pin_zone_share_while_rule_on': share(group, 'pin_rule_turns', 'rule_turns'),
            'stalled_turns': both(group, 'stalled_turns'),
            'stalled_share_of_rule_turns': share(group, 'stalled_turns', 'rule_turns'),
            'stalled_turns_inside_home': both(group, 'stalled_home_turns'),
            'games_stalled_inside_home': games_with(group, 'first_stall_home'),
            'first_stall_median': med(group, 'first_stall'),
            'door_chances_stalled': both(group, 'door_stalled'),
            'door_taken_stalled': both(group, 'door_stalled_taken'),
            'door_chances_not_stalled': both(group, 'door_other'),
            'door_taken_not_stalled': both(group, 'door_other_taken'),
            'deaths_wall_or_self_rounds_0_100': death_sum(group, ('wall', 'self')),
            'deaths_all_rounds_0_100': death_sum(group, REASONS),
            'queen_deaths_by_round_100': {t: sum(1 for p in group if p[t]['queen_death_round'] is not None and
                                                 p[t]['queen_death_round'] <= DEATH_ROUNDS) for t in tags},
            'queen_deaths_whole_game': games_with(group, 'queen_death_round'),
            'splits_by_round_100': both(group, 'splits_100'),
            'timeouts': both(group, 'tle'),
            'cpu_points_max': {t: max((p[t]['points_max'] for p in group), default=0) for t in tags},
        }

    def judge(blk):
        """The pass rule's per-layout answers."""
        n = blk['games']
        eb, ec = blk['first_exit_median']['base'], blk['first_exit_median']['candidate']
        out = blk['outside_share_rounds_30_59']['candidate']
        pearls = blk['pearls_by_round_100_median']['candidate']
        stalls = blk['games_stalled_inside_home']
        return {
            'problem_seen': n >= MIN_LAYOUT and stalls['base'] >= TARGET_SHARE * n and (eb is None or eb > EXIT_MAX),
            'fires': stalls['candidate'] == n,
            'leaves': ec is not None and ec <= EXIT_MAX and (eb is None or eb - ec >= EXIT_GAIN),
            'stays_out': out is not None and out >= OUT_SHARE,
            'pearls': pearls is not None and pearls > PEARL_WRONG,
            'card_first_exit_by_round_30': ec is not None and ec <= EXIT_TARGET,
            'card_pearls_15_by_round_100': pearls is not None and pearls >= PEARL_TARGET,
        }

    w, o = block(walled), block(other)
    by_map = {m: block([p for p in pairs if p['map'] == m]) for m in sorted({p['map'] for p in pairs})}
    layouts = {}
    for m in sorted({p['map'] for p in walled}):
        layouts[m] = block([p for p in walled if p['map'] == m])
        layouts[m]['rule'] = judge(layouts[m])
        layouts[m]['centre_rule_rounds'] = next(p['base']['center_rounds'] for p in walled if p['map'] == m)
        layouts[m]['home_tiles'] = next(p['base']['home_tiles'] for p in walled if p['map'] == m)
    seen = {m: e for m, e in layouts.items() if e['rule']['problem_seen']}
    silent = sum(1 for p in pairs if p['silent_ok'])
    target_seen = bool(seen)
    checks = {
        'target_seen': target_seen,
        'fires': target_seen and all(e['rule']['fires'] for e in seen.values()),
        'nothing_else_changes': silent == len(pairs),
        'leaves': target_seen and all(e['rule']['leaves'] for e in seen.values()),
        'stays_out': target_seen and all(e['rule']['stays_out'] for e in seen.values()),
        'pearls': target_seen and all(e['rule']['pearls'] for e in seen.values()),
    }
    passed = all(checks.values())

    def show(v):
        return 'never' if v is None else v

    def lines(m, e):
        r = e['rule']
        verdict = ('base does not show the problem, not judged' if not r['problem_seen'] else
                   'candidate leaves' if r['leaves'] and r['stays_out'] and r['pearls'] and r['fires'] else
                   'candidate does not do what the card expects')
        return (
            f"{m} ({e['games']} games, home {e['home_tiles']} tiles, centre rule {e['centre_rule_rounds']} rounds): "
            f"{verdict}. Stall test true inside the home in {e['games_stalled_inside_home']['base']} base and "
            f"{e['games_stalled_inside_home']['candidate']} candidate games (median first stalled round "
            f"{show(e['first_stall_median']['candidate'])}). First round with a head outside, per game: base "
            f"{[show(v) for v in e['first_exit_rounds']['base']]} (median {show(e['first_exit_median']['base'])}), "
            f"candidate {[show(v) for v in e['first_exit_rounds']['candidate']]} (median "
            f"{show(e['first_exit_median']['candidate'])}; gate {EXIT_MAX}, card target {EXIT_TARGET}). Turns in "
            f"rounds 30-59 that start outside: base {e['turns_outside_rounds_30_59']['base']}/"
            f"{e['turns_rounds_30_59']['base']}, candidate {e['turns_outside_rounds_30_59']['candidate']}/"
            f"{e['turns_rounds_30_59']['candidate']} (share {e['outside_share_rounds_30_59']['candidate']}; gate "
            f"{OUT_SHARE}). Pearls by round 100, per game: base {e['pearls_by_round_100']['base']}, candidate "
            f"{e['pearls_by_round_100']['candidate']} (gate: median above {PEARL_WRONG}; card target "
            f"{PEARL_TARGET}). At the door while stalled: base stepped out {e['door_taken_stalled']['base']} of "
            f"{e['door_chances_stalled']['base']} times, candidate {e['door_taken_stalled']['candidate']} of "
            f"{e['door_chances_stalled']['candidate']}; not stalled, candidate "
            f"{e['door_taken_not_stalled']['candidate']} of {e['door_chances_not_stalled']['candidate']}. Share of "
            f"centre-rule turns in the pin zone: base {e['pin_zone_share_while_rule_on']['base']}, candidate "
            f"{e['pin_zone_share_while_rule_on']['candidate']}. Tiles visited by round 100 (median): base "
            f"{e['tiles_visited_by_round_100_median']['base']}, candidate "
            f"{e['tiles_visited_by_round_100_median']['candidate']}. Wins {e['wins']['base']} -> "
            f"{e['wins']['candidate']} of {e['games']} (not a verdict).")

    dw, do = w['deaths_wall_or_self_rounds_0_100'], o['deaths_wall_or_self_rounds_0_100']
    failed = [k for k, v in checks.items() if not v]
    note = (
        f"{'PASS' if passed else 'FAIL'} ({'all six checks' if passed else 'failed: ' + ', '.join(failed)}). "
        f"{len(pairs)} paired games, {len(walled)} with a walled start for us on {len(layouts)} layout(s); base "
        f"shows the card's problem (stalls inside the home, median first exit after round {EXIT_MAX} or never) on "
        f"{len(seen)}. " + ' '.join(lines(m, e) for m, e in layouts.items()) +
        f" Same game up to the candidate's first stalled turn in {silent}/{len(pairs)} pairs. Side effects, rounds "
        f"0-100: our wall or own-body deaths on walled-start games {dw['base']} -> {dw['candidate']}, on the other "
        f"{len(other)} games {do['base']} -> {do['candidate']}; queen deaths "
        f"{w['queen_deaths_by_round_100']['base']} -> {w['queen_deaths_by_round_100']['candidate']} and "
        f"{o['queen_deaths_by_round_100']['base']} -> {o['queen_deaths_by_round_100']['candidate']}. On the other "
        f"games the stall test was true on share {o['stalled_share_of_rule_turns']['candidate']} of the "
        f"candidate's centre-rule turns (wins {o['wins']['base']} -> {o['wins']['candidate']} of {len(other)}, not "
        f"a verdict). Timeouts {total(pairs, 'base', 'tle')} -> {total(pairs, 'candidate', 'tle')}.")
    out = {
        'passed': passed,
        'note': note,
        'target_seen': target_seen,
        'checks': checks,
        'thresholds': {'MIN_LAYOUT': MIN_LAYOUT, 'TARGET_SHARE': TARGET_SHARE, 'EXIT_MAX': EXIT_MAX,
                       'EXIT_GAIN': EXIT_GAIN, 'OUT_SHARE': OUT_SHARE, 'PEARL_WRONG': PEARL_WRONG,
                       'EXIT_TARGET': EXIT_TARGET, 'PEARL_TARGET': PEARL_TARGET, 'STALL_ROUNDS': STALL_ROUNDS,
                       'ROOM_SHARE': ROOM_SHARE, 'PIN_SLACK': PIN_SLACK},
        'built_as': BUILT_AS,
        'games': len(pairs),
        'walled_start_games': len(walled),
        'layouts_with_the_problem': sorted(seen),
        'pairs_same_until_first_stalled_turn': silent,
        'walled_start_layouts': layouts,
        'walled_start_all': w,
        'other_games': o,
        'by_map': by_map,
        'limits': 'The stall clock is rebuilt from head positions in the replay, not read from the bot; whether a '
                  'pearl was in range on a turn (the pull is off then in both builds) is not rebuilt. A door chance '
                  'says a step outside was open, not that the bot scored it. The local opponent is our own release, '
                  'which stays home on a walled start, so pearls outside the home are uncontested here and wins '
                  'say little. Four games a layout; deaths and queen deaths are small counts.',
        'pairs': pairs,
    }
    with open(a.output, 'w') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print(note)


if __name__ == '__main__':
    main()
