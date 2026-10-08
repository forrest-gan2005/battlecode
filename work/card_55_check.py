#!/usr/bin/env python3
"""Card #55 queen-fallback mechanism check, attempt 2 (QUEEN_FALLBACK): when our queen is outnumbered, does she
fall back, that is, end her turn nearer to her start tile or to her last spot with company?

usage: python3 work/card_55_check.py --replays DIR --base base --candidate candidate --output FILE
Reads paired replays DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1; side 0 = we are team A).

Words (all rebuilt from the replay, no map names):
  queen          our dragon with id 0 or 1. Her length decides the game; a dead queen scores 0.
  view           the 7x7 square of tiles around her head (the map wraps round), at the start of her turn.
  outnumbered    enemy heads >= our heads in view, herself counted. A draw counts (Zhe's answer), so alone with one
                 enemy head is outnumbered. Enemy heads are those in view this turn plus those she had in view on
                 one of the last 3 rounds (jun's revision: an enemy that stepped out of view is still there).
                 Our heads are only those in view this turn.
  home           the tile her head stood on at the start of the game.
  company spot   the tile where the nearest teammate's head stood, the last time she had a teammate's head in view
                 and was not outnumbered; kept 40 rounds, and dropped when she is outnumbered within 2 steps on
                 foot of it (she is there and it gave her no upper hand). In attempt 1 it was her own tile.
  targets        home and the company spot. "Nearer target" = the one fewer steps away on foot (real walls, no
                 portals, bodies ignored; home on a tie), "other target" = the second one when both exist.
  holding        outnumbered within 2 steps on foot of home. The build keeps her inside those 2 steps and does
                 not pull further, so these turns are counted apart.
  off the target an outnumbered turn that is not holding and has a target she can walk to.
  ends nearer    fewer steps on foot to that target after her turn than before it.
  way open       (rebuilt, approximate) a free first step toward the target that no enemy head in view can reach
                 this turn: not next to an enemy head, and not within the steps an enemy dragon other than their
                 queen gets this turn (free steps = length / 4 rounded up, or up to 3 by paying length).
  nearest mate   the fewest steps on foot from her head to any teammate's head anywhere on the map (not only in
                 view), teammates taken where they stood when her turn began.

Expectation, written before any switch-on game of this build was played (thresholds are the constants below):
  1. target seen: base has at least MIN_OUT_TURNS outnumbered queen turns, in at least MIN_GAME_SHARE of the games,
     and the candidate has at least MIN_OFF_TURNS outnumbered turns off the target.
  2. nothing else changes: every pair plays the same game up to the round of the candidate's first outnumbered
     queen turn (the card: when she is not outnumbered she moves as with the switch off).
  3. falls back: of the candidate's outnumbered turns off the target, at least FALL_SHARE end nearer to one of her
     targets (the card: "reduce her path distance to her start tile, or to the nearest tile she remembers with
     more of ours than theirs, in most such turns"), and that share is at least FALL_GAIN higher than base's.
passed = all three.
What changed from the attempt-1 check, and why: the build changed (jun's revision: fall back first, keep away only
between steps equally good for the target; enemy heads of the last 3 rounds still count), so "outnumbered" here has
the 3-round memory, the keep-away gate is gone (keep-away is now a tie-break, its numbers are still reported) and
the fall-back gate is the card's own wording over all outnumbered turns off the target, not only the turns where
attempt 1 left the pull on. The thresholds were written before this file was run on any replay. It was then run
on attempt 1's replays (the old build, and the same base games) to find bugs in the counting. That run showed one
thing about the build, not the gates: with the company spot as her own tile she is within 2 steps of it when
almost every spell starts (a target on 2 of 124 base turns), so the build and this check now take the teammate's
tile. With that spot base already ends nearer to one of her targets on 53% of those turns, so the gate asks the
candidate for about 68%. No threshold was changed after the first run.
Reported, not part of the verdict: the same rows as attempt 1 (keep-away, first outnumbered turn of each pair,
rule on-and-off, queen alive at round 100 and 150, how she died, her length and pearls, team pearls, time near
home, wins, timeouts), the share that ends nearer the nearer target only, the split by rebuilt "way open", what she
does while holding and on turns she is outnumbered by memory alone, and the two counts jun asked for: the change in
steps on foot to the nearest teammate head on outnumbered turns, and how many of her turns pass from her first
outnumbered turn until a teammate's head is within MATE_NEAR steps on foot.
"""
import argparse, concurrent.futures as cf, glob, hashlib, json, os, statistics, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# PASS RULE (fixed before any switch-on game of this build was played)
MIN_OUT_TURNS = 40     # outnumbered queen turns base must show over the whole run
MIN_GAME_SHARE = 0.5   # share of base games with at least one outnumbered queen turn
MIN_OFF_TURNS = 30     # candidate outnumbered turns off the target needed to judge the fall-back
FALL_SHARE = 0.50      # candidate: share of those turns that end nearer to one of her targets ("most")
FALL_GAIN = 0.15       # ... and that share minus base's

# The bot's settings this check mirrors (mybot2/main.cpp).
VIEW = 3               # VISION_RADIUS
GHOST = 3              # GHOST_ROUNDS: an enemy head counts for this many rounds after she last saw it
MEMORY = 40            # QF_MEMORY
HOLD = 2               # QF_HOLD
GUARD_RADIUS = 5       # QF_GUARD_RADIUS, reported only
PAY_REACH = 3          # QS_PAY_REACH
KEEP = 2               # shortest a dragon can get by paying length

LAST_TURNS = 3         # "outnumbered before she died" looks at her last this-many turns
FLIP_GAP = 3           # the rule coming back on within this many of her turns counts as off-and-on
HOME_NEAR = 6          # "near home" = this many steps on foot or fewer
HOME_FROM = 60         # time near home is counted from this round
MATE_NEAR = 3          # "a teammate is near" = its head this many steps on foot or fewer from hers
REASONS = ['wall', 'self', 'body', 'head-on', 'no action']
CLASSES = ('nearer_open', 'other_open', 'shut')
BUILT_AS = (
    "How attempt 2 is built (switch QUEEN_FALLBACK, off by default). Each turn the queen counts heads: ours are "
    "herself plus teammates' heads in her 7x7 view; theirs are enemy heads in view plus enemy heads she saw in the "
    "last 3 rounds (jun's revision 3). Theirs >= ours is outnumbered (a draw counts, Zhe's answer 1) and the rule "
    "is on exactly on those turns (answer 4). Targets are her start tile and the company spot (answer 3). While on: "
    "(a) the nearer target on foot is tried first; its way is open when a free first step toward it is one no enemy "
    "head in view can reach this turn; if it is shut the other target is tried (revision 2); (b) with a way open, "
    "the pull to that target leads: 30000 points per step gained on foot, above keep-away, pearls, room and her "
    "few-turns-ahead threat charge, so keep-away (1500 points per tile inside 5 tiles of an enemy head, heads of "
    "the last 3 rounds included) only ranks steps equally good for the target (revision 1); (c) with both ways "
    "shut, this turn is the attempt-1 order: keep-away leads and a 300-point pull to the nearer target breaks "
    "ties; (d) her existing safety stays above the pull: tiles an enemy head can reach this turn (card 39's hit "
    "and pay charges), dead ends and short-of-room steps (such a step is ranked as two steps worse for the target "
    "than it is, so the pull can never buy it), and for a queen of 8 or longer the existing least-exposed-tile "
    "rule; (e) the opening centre pull, card 51's pull to unseen tiles and the barren-area route are off for her "
    "while the rule is on. It applies on every map size, all game. Builder's readings, say if wrong: within 2 "
    "steps on foot of a target she is 'there'. At home the pull then only keeps her inside those 2 steps (the rule "
    "stays on, as answer 4 says, but there is nothing nearer to go to). At the company spot, still outnumbered, "
    "the spot is dropped and she goes on to home, so a spot only pulls her from 3 steps or more away. ONE CHANGE "
    "NOBODY ASKED FOR: the company spot is now the tile where the nearest teammate's head stood on her last turn "
    "with company, not her own tile as in attempt 1. With her own tile she is within 2 steps of the spot when "
    "almost every outnumbered spell starts (in attempt 1's replays it would have been a target on 2 of 124 base "
    "turns), so 'head to where we have the upper hand' and the 'other target' of revision 2 would never happen; "
    "say so and it goes back. Also: a first step blocked by her own body counts as a shut way, like one an enemy "
    "can reach; a company spot still needs a teammate's head in view and not outnumbered; her rule for going at "
    "the enemy queen runs before step scoring and is not changed; teammates do nothing new.")


def gap(a, b, size):
    raw = abs(a - b)
    return min(raw, size - raw)


class Board:
    """Walls and start dragons of the map text inside a replay."""

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
        self._walks = {}

    def far(self, a, b):
        """Straight-line distance with wrap-around, as the bot's keep-away measures it."""
        W = self.W
        return gap(a % W, b % W, W) + gap(a // W, b // W, self.H)

    def in_view(self, head, cell):
        W = self.W
        return gap(cell % W, head % W, W) <= VIEW and gap(cell // W, head // W, self.H) <= VIEW

    def spread(self, starts, limit=None, blocked=()):
        """Steps on foot from every tile to the nearest of `starts`: open sides only, -1 = no way or past `limit`."""
        dist = [-1] * (self.W * self.H)
        queue = deque()
        for s in starts:
            if dist[s] < 0:
                dist[s] = 0
                queue.append(s)
        while queue:
            c = queue.popleft()
            if limit is not None and dist[c] >= limit:
                continue
            for d in range(4):
                n = self.nb[c][d]
                if self.side[c][d] == 0 and dist[n] < 0 and n not in blocked:
                    dist[n] = dist[c] + 1
                    queue.append(n)
        return dist

    def walk(self, start):
        """Steps on foot from every tile to `start`, bodies ignored."""
        dist = self._walks.get(start)
        if dist is None:
            dist = self._walks[start] = self.spread([start])
        return dist


def scan(path, ours):
    """One pass over a replay for our side."""
    root = replay.load(path).root()
    board = Board(root.text(0))
    W = board.W
    result = root.pointer(4)
    winner = ('A', 'B')[result.u16(6)] if result.u16(4) == 1 else None
    bodies = {i: deque(b) for i, b in board.bodies.items()}
    team_of = dict(board.team_of)
    queen = next((i for i in (0, 1) if team_of.get(i) == ours), None)
    if queen is None:
        raise ValueError(f'{path}: no queen for team {ours}')
    their_queen = 1 - queen
    home = bodies[queen][0]
    to_home = board.walk(home)

    stat = {k: 0 for k in (
        'q_turns', 'out_turns', 'out_view_turns', 'out_memory_only', 'out_alone', 'out_done', 'out_moved',
        'foe_turns', 'away', 'closer', 'closes_any', 'inside_guard_end', 'ends_next_to_enemy',
        'off_turns', 'off_either', 'off_nearer', 'off_farther', 'off_nearer_is_spot', 'off_two_targets',
        'mem_off_turns', 'mem_off_either',
        'hold_turns', 'hold_kept', 'home_turns', 'home_nearer',
        'mate_turns', 'mate_nearer', 'mate_farther', 'mate_start_sum', 'mate_change_sum',
        'died_on_out_turn', 'episodes', 'restarts',
        'late_turns', 'late_near_home', 'pearls_100', 'q_pearls_100', 'q_pearls', 'tle', 'points_max')}
    for c in CLASSES:
        stat[f'{c}_turns'] = stat[f'{c}_ok'] = 0
    seen = {}              # enemy id -> last round its head was in her view
    spot = spot_round = None
    pend = None            # her outnumbered turn in progress
    first = None           # her first outnumbered turn of the game
    first_out = None
    recent = deque(maxlen=LAST_TURNS)   # outnumbered or not, her last turns
    was_out = False
    since_off = None       # her turns since the rule last went off
    waited = None          # her turns since her first outnumbered turn, while no teammate is near
    mate_after = None      # ... and the count when one first was
    q_death = q_reason = None
    out_before_death = None
    q_len = {100: None, 150: None}
    digests, h = {}, hashlib.sha1()
    rnd = 0

    def mine(did):
        return team_of.get(did) == ours

    def settle():
        """Close her outnumbered turn: where did she end?"""
        nonlocal pend
        if pend is None:
            return
        p, pend = pend, None
        body = bodies.get(queen)
        if not body:
            stat['died_on_out_turn'] += 1
            p['died'] = True
            return
        end = body[0]
        start = p['start']
        p['end'] = end
        stat['out_done'] += 1
        stat['out_moved'] += end != start
        if p['foes']:
            before = min(board.far(start, f) for f in p['foes'])
            after = min(board.far(end, f) for f in p['foes'])
            p.update(away=after > before, closer=after < before)
            stat['foe_turns'] += 1
            stat['away'] += after > before
            stat['closer'] += after < before
            stat['closes_any'] += any(board.far(end, f) < board.far(start, f) for f in p['foes'])
            stat['inside_guard_end'] += after <= GUARD_RADIUS
            stat['ends_next_to_enemy'] += after <= 1
        t1, t2, cls = p['t1'], p['t2'], p['cls']
        if cls == 'hold':
            stat['hold_turns'] += 1
            stat['hold_kept'] += 0 <= to_home[end] <= HOLD
        elif t1 is not None:
            nearer = 0 <= t1[end] < t1[start]
            other = t2 is not None and 0 <= t2[end] < t2[start]
            p.update(nearer=nearer, either=nearer or other)
            stat['off_turns'] += 1
            stat['off_nearer'] += nearer
            stat['off_either'] += nearer or other
            stat['off_farther'] += t1[end] < 0 or t1[end] > t1[start]
            stat['off_nearer_is_spot'] += p['spot_first']
            stat['off_two_targets'] += t2 is not None
            if not p['foes']:
                stat['mem_off_turns'] += 1
                stat['mem_off_either'] += nearer or other
            stat[f'{cls}_turns'] += 1
            if cls == 'nearer_open':
                stat[f'{cls}_ok'] += nearer
            elif cls == 'other_open':
                stat[f'{cls}_ok'] += other
            else:
                stat[f'{cls}_ok'] += bool(p.get('away'))
        if to_home[start] >= 1:
            stat['home_turns'] += 1
            stat['home_nearer'] += 0 <= to_home[end] < to_home[start]
        mates = p['mates']
        if mates is not None and mates[start] >= 0 and mates[end] >= 0:
            stat['mate_turns'] += 1
            stat['mate_nearer'] += mates[end] < mates[start]
            stat['mate_farther'] += mates[end] > mates[start]
            stat['mate_start_sum'] += mates[start]
            stat['mate_change_sum'] += mates[end] - mates[start]

    def queen_turn():
        nonlocal spot, spot_round, pend, first, first_out, was_out, since_off, waited, mate_after
        body = bodies[queen]
        head = body[0]
        friends, foes, mates = [], [], []
        danger = set()
        taken = set()
        for b in bodies.values():
            taken.update(b)
        for did, b in bodies.items():
            if not b or did == queen:
                continue
            if mine(did):
                mates.append(b[0])
            if not board.in_view(head, b[0]):
                continue
            if mine(did):
                friends.append(b[0])
                continue
            foes.append(b[0])
            seen[did] = rnd
            # Tiles this enemy head can enter this turn, as the bot's card-39 map counts them.
            danger.update(n for d, n in enumerate(board.nb[b[0]]) if board.side[b[0]][d] == 0)
            if did != their_queen:
                free = max(1, (len(b) + 3) // 4)
                reach = max(free, min((len(b) + 3) // 4 + len(b) - KEEP, PAY_REACH))
                field = board.spread([b[0]], reach, taken)
                danger.update(c for c, v in enumerate(field) if v > 0)
        theirs = sum(1 for r in seen.values() if rnd - r <= GHOST)
        out = theirs >= 1 + len(friends)
        stat['q_turns'] += 1
        recent.append(out)
        if rnd >= HOME_FROM:
            stat['late_turns'] += 1
            stat['late_near_home'] += 0 <= to_home[head] <= HOME_NEAR
        if (out or waited is not None) and mate_after is None:
            # jun's count: her turns from the first outnumbered turn until a teammate's head is near on foot.
            waited = 0 if waited is None else waited + 1
            near = board.spread([head], MATE_NEAR)
            if any(near[m] >= 0 for m in mates):
                mate_after = waited
        if not out:
            if friends:
                spot, spot_round = min(friends, key=lambda f: (board.far(head, f), f)), rnd
            if was_out:
                since_off = 0
            elif since_off is not None:
                since_off += 1
            was_out = False
            return
        stat['out_turns'] += 1
        stat['out_view_turns'] += len(foes) >= 1 + len(friends)
        stat['out_memory_only'] += not foes
        stat['out_alone'] += not friends
        if not was_out:
            stat['episodes'] += 1
            stat['restarts'] += since_off is not None and since_off < FLIP_GAP
        was_out = True
        if first_out is None:
            first_out = rnd
        # Targets: home and the company spot; the nearer on foot first, home on a tie.
        to_spot = board.walk(spot) if spot is not None and rnd - spot_round <= MEMORY else None
        home_d = to_home[head]
        spot_d = to_spot[head] if to_spot is not None else -1
        if 0 <= spot_d <= HOLD:
            # Outnumbered at the spot: it is dropped.
            spot = to_spot = None
            spot_d = -1
        spot_first = spot_d >= 0 and (home_d < 0 or spot_d < home_d)
        t1 = t2 = None
        if spot_first:
            t1, t2 = to_spot, (to_home if home_d >= 0 else None)
        elif home_d >= 0:
            t1, t2 = to_home, (to_spot if spot_d >= 0 else None)

        def way(field, hold):
            if hold and field[head] <= HOLD:
                return True
            for d in range(4):
                n = board.nb[head][d]
                if board.side[head][d] == 0 and n not in taken and n not in danger and 0 <= field[n] < field[head]:
                    return True
            return False

        if t1 is None:
            cls = None
        elif not spot_first and home_d <= HOLD:
            cls = 'hold'
        elif way(t1, not spot_first):
            cls = 'nearer_open'
        elif t2 is not None and way(t2, spot_first):
            cls = 'other_open'
        else:
            cls = 'shut'
        pend = {'round': rnd, 'start': head, 'foes': foes, 'friends': len(friends), 't1': t1, 't2': t2, 'cls': cls,
                'spot_first': spot_first, 'mates': board.spread(mates) if mates else None}
        if first is None:
            first = pend

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else '?'
        pl = ev.pointer(0)
        if kind == 'roundStart':
            settle()
            digests[rnd] = h.hexdigest()
            rnd = pl.i32(0)
            h = hashlib.sha1()
            if rnd in q_len:
                q_len[rnd] = len(bodies[queen]) if bodies.get(queen) else 0
        elif kind == 'turnStart':
            settle()
        elif kind == 'dragonAction':
            settle()
            did = pl.i32(0)
            if not mine(did) or not bodies.get(did):
                continue
            usage = pl.pointer(1)
            stat['points_max'] = max(stat['points_max'], usage.u64(0) if usage else 0)
            stat['tle'] += pl.bit(32)
            if did == queen:
                queen_turn()
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
            while len(body) > 1 and body[-1] != tail:
                body.pop()
            if mine(did) and before > 0 and len(body) > before:
                stat['pearls_100'] += rnd <= 100
                if did == queen:
                    stat['q_pearls'] += 1
                    stat['q_pearls_100'] += rnd <= 100
        elif kind == 'dragonSplit':
            parent, child = pl.i32(0), pl.i32(4)
            h.update(f's{parent}{child}'.encode())
            team = ('A', 'B')[pl.u16(8)]
            for did, part in ((parent, pl.pointer(0)), (child, pl.pointer(1))):
                bodies[did] = deque(replay.point(p)[1] * W + replay.point(p)[0] for p in part)
                team_of[did] = team
        elif kind == 'dragonDeath':
            did, reason = pl.i32(0), pl.u16(4)
            h.update(f'd{did}{reason}'.encode())
            bodies.pop(did, None)
            if did == queen and q_death is None:
                q_death = rnd
                q_reason = REASONS[reason] if reason < len(REASONS) else str(reason)
                out_before_death = any(recent)
                settle()
    settle()
    digests[rnd] = h.hexdigest()
    alive = bool(bodies.get(queen))
    for mark in q_len:
        if q_len[mark] is None:
            q_len[mark] = len(bodies[queen]) if alive else 0
    if first is not None:
        first = {'enemy_heads_in_view': len(first['foes']),
                 **{k: first.get(k) for k in ('round', 'start', 'end', 'friends', 'cls', 'away', 'closer', 'nearer',
                                              'either', 'died')}}
    if first_out is None:
        mate_wait = None
    elif mate_after is not None:
        mate_wait = 'reached'
    else:
        mate_wait = 'queen died first' if q_death is not None else 'game ended first'
    return {'digests': digests, 'size': [board.W, board.H], 'tiles': board.W * board.H, 'rounds': rnd,
            'win': int(winner == ours), 'first_out_round': first_out, 'first_out_turn': first,
            'queen_death_round': q_death, 'queen_death_reason': q_reason, 'outnumbered_before_death': out_before_death,
            'queen_len_100': q_len[100], 'queen_len_150': q_len[150], 'queen_len_end': len(bodies[queen]) if alive else 0,
            'mate_wait': mate_wait, 'mate_wait_turns': mate_after if mate_after is not None else waited,
            **stat}


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


def mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 2) if values else None


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

    tags = ('base', 'candidate')
    pairs = []
    for n, k in enumerate(keys):
        b, c = scans[2 * n], scans[2 * n + 1]
        diff = first_diff(b.pop('digests'), c.pop('digests'))
        fb, fc = b['first_out_turn'], c['first_out_turn']
        same_start = bool(fb and fc and fb['round'] == fc['round'] and fb['start'] == fc['start'])
        pairs.append({'map': k[0], 'seed': k[1], 'side': k[2], 'first_diff_round': diff,
                      'silent_ok': diff is None or (c['first_out_round'] is not None and diff >= c['first_out_round']),
                      'first_turn_same_position': same_start,
                      'first_turn_moves_differ': bool(same_start and fb.get('end') != fc.get('end')),
                      'base': b, 'candidate': c})

    def total(group, tag, field):
        return sum(int(p[tag][field] or 0) for p in group)

    def both(group, field):
        return {t: total(group, t, field) for t in tags}

    def share(group, top, bottom):
        return {t: ratio(total(group, t, top), total(group, t, bottom)) for t in tags}

    def games(group, test):
        return {t: sum(1 for p in group if test(p[t])) for t in tags}

    def wait(group, tag):
        """jun's count: her turns from her first outnumbered turn until a teammate's head is near on foot."""
        rows = [p[tag] for p in group if p[tag]['mate_wait'] is not None]
        got = sorted(s['mate_wait_turns'] for s in rows if s['mate_wait'] == 'reached')
        return {'games_with_an_outnumbered_turn': len(rows),
                'teammate_came_near': len(got),
                'already_near_on_that_turn': sum(1 for v in got if v == 0),
                'near_within_5_turns': sum(1 for v in got if v <= 5),
                'near_within_10_turns': sum(1 for v in got if v <= 10),
                'turns_median': statistics.median(got) if got else None,
                'turns_mean': mean(got),
                'turns_each': got,
                'queen_died_first': sum(1 for s in rows if s['mate_wait'] == 'queen died first'),
                'game_ended_first': sum(1 for s in rows if s['mate_wait'] == 'game ended first')}

    def block(group):
        firsts = [p for p in group if p['first_turn_same_position']]
        differ = [p for p in firsts if p['first_turn_moves_differ']]

        def first_count(sel, tag, field):
            return sum(1 for p in sel if p[tag]['first_out_turn'].get(field))

        deaths = {t: {} for t in tags}
        for p in group:
            for t in tags:
                r = p[t]['queen_death_reason']
                if r is not None:
                    deaths[t][r] = deaths[t].get(r, 0) + 1
        return {
            'games': len(group),
            'queen_turns': both(group, 'q_turns'),
            'outnumbered_turns': both(group, 'out_turns'),
            'outnumbered_share_of_queen_turns': share(group, 'out_turns', 'q_turns'),
            'outnumbered_counting_only_heads_in_view': both(group, 'out_view_turns'),
            'outnumbered_with_no_enemy_head_in_view': both(group, 'out_memory_only'),
            'outnumbered_turns_with_no_teammate_in_view': both(group, 'out_alone'),
            'games_with_an_outnumbered_turn': games(group, lambda s: s['out_turns'] > 0),
            'first_outnumbered_round_mean': {t: mean([p[t]['first_out_round'] for p in group]) for t in tags},
            'turns_off_the_target': both(group, 'off_turns'),
            'ends_nearer_one_of_her_targets': both(group, 'off_either'),
            'ends_nearer_one_of_her_targets_share': share(group, 'off_either', 'off_turns'),
            'ends_nearer_the_nearer_target': both(group, 'off_nearer'),
            'ends_nearer_the_nearer_target_share': share(group, 'off_nearer', 'off_turns'),
            'ends_farther_from_the_nearer_target_share': share(group, 'off_farther', 'off_turns'),
            'nearer_target_was_the_company_spot': both(group, 'off_nearer_is_spot'),
            'turns_with_two_targets': both(group, 'off_two_targets'),
            'ends_nearer_home_share': share(group, 'home_nearer', 'home_turns'),
            'way_open_to_nearer_target_turns': both(group, 'nearer_open_turns'),
            'way_open_to_nearer_target_ends_nearer_it_share': share(group, 'nearer_open_ok', 'nearer_open_turns'),
            'way_open_to_other_target_only_turns': both(group, 'other_open_turns'),
            'way_open_to_other_target_only_ends_nearer_it_share': share(group, 'other_open_ok', 'other_open_turns'),
            'both_ways_shut_turns': both(group, 'shut_turns'),
            'both_ways_shut_ends_farther_from_enemy_share': share(group, 'shut_ok', 'shut_turns'),
            'no_enemy_in_view_turns_off_the_target': both(group, 'mem_off_turns'),
            'no_enemy_in_view_ends_nearer_a_target_share': share(group, 'mem_off_either', 'mem_off_turns'),
            'holding_turns': both(group, 'hold_turns'),
            'holding_ends_within_2_steps_of_home_share': share(group, 'hold_kept', 'hold_turns'),
            'turns_with_an_enemy_head_in_view': both(group, 'foe_turns'),
            'ends_farther_from_nearest_enemy_head': both(group, 'away'),
            'ends_farther_share': share(group, 'away', 'foe_turns'),
            'ends_nearer_to_nearest_enemy_head': both(group, 'closer'),
            'ends_nearer_share': share(group, 'closer', 'foe_turns'),
            'ends_nearer_to_any_enemy_head_in_view': both(group, 'closes_any'),
            'ends_within_5_tiles_of_an_enemy_head_share': share(group, 'inside_guard_end', 'foe_turns'),
            'ends_next_to_an_enemy_head': both(group, 'ends_next_to_enemy'),
            'moved_share': share(group, 'out_moved', 'out_done'),
            'died_on_an_outnumbered_turn': both(group, 'died_on_out_turn'),
            'nearest_teammate_turns_measured': both(group, 'mate_turns'),
            'nearest_teammate_ends_nearer_share': share(group, 'mate_nearer', 'mate_turns'),
            'nearest_teammate_ends_farther_share': share(group, 'mate_farther', 'mate_turns'),
            'nearest_teammate_steps_at_turn_start_mean': {
                t: ratio(total(group, t, 'mate_start_sum'), total(group, t, 'mate_turns'), 2) for t in tags},
            'nearest_teammate_steps_change_per_turn_mean': {
                t: ratio(total(group, t, 'mate_change_sum'), total(group, t, 'mate_turns'), 2) for t in tags},
            'turns_until_a_teammate_is_near': {t: wait(group, t) for t in tags},
            'rule_on_spells': both(group, 'episodes'),
            'spells_restarting_within_3_turns': both(group, 'restarts'),
            'first_turn_pairs_same_position': len(firsts),
            'first_turn_moves_differ': len(differ),
            'first_turn_ends_farther': {t: first_count(firsts, t, 'away') for t in tags},
            'first_turn_ends_nearer_enemy': {t: first_count(firsts, t, 'closer') for t in tags},
            'first_turn_ends_nearer_a_target': {t: first_count(firsts, t, 'either') for t in tags},
            'queen_alive_round_100': games(group, lambda s: s['queen_len_100'] > 0),
            'queen_alive_round_150': games(group, lambda s: s['queen_len_150'] > 0),
            'queen_alive_at_end': games(group, lambda s: s['queen_len_end'] > 0),
            'queen_deaths_by_cause': deaths,
            'queen_deaths_outnumbered_on_last_3_turns': games(group, lambda s: bool(s['outnumbered_before_death'])),
            'queen_deaths_not_outnumbered_on_last_3_turns': games(
                group, lambda s: s['queen_death_round'] is not None and not s['outnumbered_before_death']),
            'queen_length_round_100_mean': {t: mean([p[t]['queen_len_100'] for p in group]) for t in tags},
            'queen_length_round_150_mean': {t: mean([p[t]['queen_len_150'] for p in group]) for t in tags},
            'queen_length_end_mean': {t: mean([p[t]['queen_len_end'] for p in group]) for t in tags},
            'queen_pearls_by_round_100': both(group, 'q_pearls_100'),
            'queen_pearls': both(group, 'q_pearls'),
            'team_pearls_by_round_100': both(group, 'pearls_100'),
            'near_home_share_from_round_60': share(group, 'late_near_home', 'late_turns'),
            'wins': both(group, 'win'),
            'timeouts': both(group, 'tle'),
            'cpu_points_max': {t: max((p[t]['points_max'] for p in group), default=0) for t in tags},
        }

    w = block(pairs)
    by_map = {m: block([p for p in pairs if p['map'] == m]) for m in sorted({p['map'] for p in pairs})}
    silent = sum(1 for p in pairs if p['silent_ok'])
    n = len(pairs)
    fall = w['ends_nearer_one_of_her_targets_share']
    target_seen = (w['outnumbered_turns']['base'] >= MIN_OUT_TURNS and
                   w['games_with_an_outnumbered_turn']['base'] >= MIN_GAME_SHARE * n and
                   w['turns_off_the_target']['candidate'] >= MIN_OFF_TURNS)
    checks = {
        'target_seen': target_seen,
        'nothing_else_changes': silent == n,
        'falls_back': (target_seen and fall['candidate'] is not None and fall['candidate'] >= FALL_SHARE and
                       (fall['base'] is None or fall['candidate'] - fall['base'] >= FALL_GAIN - 1e-9)),
    }
    passed = all(checks.values())

    def pct(v):
        return 'n/a' if v is None else f'{100 * v:.0f}%'

    def two(d, f=str):
        return f"{f(d['base'])} -> {f(d['candidate'])}"

    def causes(d):
        return ', '.join(f'{k} {v}' for k, v in sorted(d.items())) or 'none'

    def waited(d):
        return (f"{d['teammate_came_near']} of {d['games_with_an_outnumbered_turn']} games "
                f"(median {d['turns_median']} turns; within 5 turns {d['near_within_5_turns']}; "
                f"queen died first {d['queen_died_first']}, game ended first {d['game_ended_first']})")

    failed = [k for k, v in checks.items() if not v]
    wt = w['turns_until_a_teammate_is_near']
    note = (
        f"{'PASS' if passed else 'FAIL'} ({'all three checks' if passed else 'failed: ' + ', '.join(failed)}). "
        f"{n} paired games on {len(by_map)} maps, base -> candidate throughout. Outnumbered queen turns "
        f"{two(w['outnumbered_turns'])} ({two(w['outnumbered_share_of_queen_turns'], pct)} of her turns; in "
        f"{two(w['games_with_an_outnumbered_turn'])} games; no teammate in view on "
        f"{two(w['outnumbered_turns_with_no_teammate_in_view'])}; no enemy head in view any more on "
        f"{two(w['outnumbered_with_no_enemy_head_in_view'])}; by attempt 1's count, heads in view only, "
        f"{two(w['outnumbered_counting_only_heads_in_view'])}). Fall-back: of her outnumbered turns off the target "
        f"({two(w['turns_off_the_target'])}) she ends nearer to one of her targets on {two(fall, pct)} (gate: "
        f"{FALL_SHARE:.2f} and +{FALL_GAIN:.2f} over base), nearer to the nearer target on "
        f"{two(w['ends_nearer_the_nearer_target_share'], pct)}, nearer home {two(w['ends_nearer_home_share'], pct)}. "
        f"Rebuilt split: way open to the nearer target {two(w['way_open_to_nearer_target_turns'])} turns, ends "
        f"nearer it {two(w['way_open_to_nearer_target_ends_nearer_it_share'], pct)}; open to the other target only "
        f"{two(w['way_open_to_other_target_only_turns'])} turns, ends nearer it "
        f"{two(w['way_open_to_other_target_only_ends_nearer_it_share'], pct)}; both shut "
        f"{two(w['both_ways_shut_turns'])} turns, ends farther from the nearest enemy head "
        f"{two(w['both_ways_shut_ends_farther_from_enemy_share'], pct)}. Holding within {HOLD} steps of home "
        f"{two(w['holding_turns'])} turns, still there after the turn "
        f"{two(w['holding_ends_within_2_steps_of_home_share'], pct)}. Keep-away (a tie-break in this build, turns "
        f"with an enemy head in view): ends farther from the nearest enemy head {two(w['ends_farther_share'], pct)}, "
        f"nearer {two(w['ends_nearer_share'], pct)}, next to one {two(w['ends_next_to_an_enemy_head'])}. Nearest "
        f"teammate head on outnumbered turns ({two(w['nearest_teammate_turns_measured'])} turns): "
        f"{two(w['nearest_teammate_steps_at_turn_start_mean'])} steps on foot at the start of the turn, change "
        f"per turn {two(w['nearest_teammate_steps_change_per_turn_mean'])}, ends nearer "
        f"{two(w['nearest_teammate_ends_nearer_share'], pct)}, farther "
        f"{two(w['nearest_teammate_ends_farther_share'], pct)}. Her turns from her first outnumbered turn until a "
        f"teammate's head is within {MATE_NEAR} steps: base {waited(wt['base'])}; candidate "
        f"{waited(wt['candidate'])}. First outnumbered turn of a pair, same position in both games: "
        f"{w['first_turn_pairs_same_position']} pairs, moves differ in {w['first_turn_moves_differ']}; ends nearer "
        f"a target {two(w['first_turn_ends_nearer_a_target'])}, farther from the enemy "
        f"{two(w['first_turn_ends_farther'])}. Same game up to the candidate's first outnumbered turn in "
        f"{silent}/{n} pairs. Rule-on spells {two(w['rule_on_spells'])}, coming back on within {FLIP_GAP} of her "
        f"turns {two(w['spells_restarting_within_3_turns'])}. What would show it is wrong (small counts, not a "
        f"verdict): queen alive at round 100 {two(w['queen_alive_round_100'])}, at 150 "
        f"{two(w['queen_alive_round_150'])}, at the end {two(w['queen_alive_at_end'])} of {n}; her deaths by cause "
        f"base [{causes(w['queen_deaths_by_cause']['base'])}], candidate "
        f"[{causes(w['queen_deaths_by_cause']['candidate'])}]; deaths with no outnumbered turn among her last "
        f"{LAST_TURNS} {two(w['queen_deaths_not_outnumbered_on_last_3_turns'])} (the card: attackers from outside "
        f"her view); her mean length at round 100 {two(w['queen_length_round_100_mean'])}, at 150 "
        f"{two(w['queen_length_round_150_mean'])}; her pearls by round 100 {two(w['queen_pearls_by_round_100'])}; "
        f"team pearls by round 100 {two(w['team_pearls_by_round_100'])}; her turns within {HOME_NEAR} steps of home "
        f"from round {HOME_FROM} {two(w['near_home_share_from_round_60'], pct)}. Wins {two(w['wins'])} of {n} (not a "
        f"verdict). Timeouts {two(w['timeouts'])}.")
    out = {
        'passed': passed,
        'note': note,
        'target_seen': target_seen,
        'checks': checks,
        'thresholds': {'MIN_OUT_TURNS': MIN_OUT_TURNS, 'MIN_GAME_SHARE': MIN_GAME_SHARE,
                       'MIN_OFF_TURNS': MIN_OFF_TURNS, 'FALL_SHARE': FALL_SHARE, 'FALL_GAIN': FALL_GAIN,
                       'VIEW': VIEW, 'GHOST': GHOST, 'MEMORY': MEMORY, 'HOLD': HOLD, 'GUARD_RADIUS': GUARD_RADIUS,
                       'PAY_REACH': PAY_REACH, 'LAST_TURNS': LAST_TURNS, 'FLIP_GAP': FLIP_GAP,
                       'HOME_NEAR': HOME_NEAR, 'HOME_FROM': HOME_FROM, 'MATE_NEAR': MATE_NEAR},
        'built_as': BUILT_AS,
        'games': n,
        'pairs_same_until_first_outnumbered_turn': silent,
        'all_games': w,
        'by_map': by_map,
        'limits': 'Outnumbered, the company spot and the targets are rebuilt from head positions in the replay, not '
                  'read from the bot. The rebuild walks the real walls; the bot walks the walls it has seen and '
                  'treats unseen sides as open, so the two can differ on a few turns. "Way open" is the roughest '
                  'part: it uses each enemy dragon\'s true length where the bot uses the parts it has seen, and it '
                  'does not rebuild her dead-end, room and exposure rules, which may still forbid the step; it is '
                  'reported, never gated. The gate counts a turn that ends nearer to either target, which a dragon '
                  'moving at random also does fairly often, so read it against base. After the first outnumbered '
                  'turn the two games of a pair are different games, so the shares compare two sets of positions; '
                  'only the first-turn rows compare the same position. A turn on which she died is in no "ends" '
                  'share. Nearest teammate is on foot over the whole map, wherever the teammate is, and does not '
                  'know whether that teammate is alone or losing. The local opponent is our own release. Four '
                  'games a map: deaths, lengths and pearls are small counts and no verdict on outcomes.',
        'pairs': pairs,
    }
    with open(a.output, 'w') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print(note)


if __name__ == '__main__':
    main()
