#!/usr/bin/env python3
"""Card #55 queen-fallback mechanism check, attempt 3 (QUEEN_FALLBACK): when our queen is outnumbered and remembers
a spot where we had more heads than they did, does she go to that spot, and no longer to her start tile?

usage: python3 work/card_55_check.py --replays DIR --base base --candidate candidate --output FILE
Reads paired replays DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1; side 0 = we are team A).

Words (all rebuilt from the replay, no map names):
  queen          our dragon with id 0 or 1. Her length decides the game; a dead queen scores 0.
  view           the 7x7 square of tiles around her head (the map wraps round), at the start of her turn.
  outnumbered    enemy heads >= our heads in view, herself counted. A draw counts (Zhe's answer), so alone with one
                 enemy head is outnumbered. Enemy heads are those in view this turn plus those she had in view on
                 one of the last 3 rounds (jun's revision). Our heads are only those in view this turn.
  home           the tile her head stood on at the start of the game.
  company spot   a tile she remembers: where the nearest teammate's head stood on a turn she had a teammate's head
                 in view and was not outnumbered, with the margin (our heads minus theirs) of that turn. She keeps
                 up to 4, each for 40 rounds; a new sighting within 6 tiles of a remembered spot replaces it; a spot
                 is dropped when she is outnumbered within 2 steps on foot of it (she is there and it gave her no
                 upper hand). Attempt 2 kept one spot and no margin.
  picked spot    the spot the rule goes for this turn. Spots are ranked by steps on foot (real walls, no portals,
                 bodies ignored), each head of margin above 1 counting as 3 steps nearer; the first one in that
                 order whose way is open is picked, or the first one when every way is shut.
  spot turn      an outnumbered turn on which she has at least one spot she can walk to.
  last resort    an outnumbered turn with no such spot. Only then is home her target (Zhe's revision); within 2
                 steps on foot of home she holds.
  ends nearer    fewer steps on foot to that tile after her turn than before it.
  way open       (rebuilt, approximate) a free first step toward the tile that no enemy head in view can reach this
                 turn: not next to an enemy head, and not within the steps an enemy dragon other than their queen
                 gets this turn (free steps = length / 4 rounded up, or up to 3 by paying length).
  nearest mate   the fewest steps on foot from her head to any teammate's head anywhere on the map (not only in
                 view), teammates taken where they stood when her turn began.

Expectation, written before any switch-on game of this build was played (thresholds are the constants below):
  1. target seen: base has at least MIN_OUT_TURNS outnumbered queen turns, in at least MIN_GAME_SHARE of the games,
     and the candidate has at least MIN_SPOT_TURNS spot turns.
  2. nothing else changes: every pair plays the same game up to the round of the candidate's first outnumbered
     queen turn (the card: when she is not outnumbered she moves as with the switch off).
  3. goes to company: of the candidate's spot turns, at least SPOT_SHARE end nearer to the picked spot (Zhe's
     revision: she "prioritizes going back to where her teammates actually had advantages in number based on recent
     memory"), and that share is at least SPOT_GAIN higher than base's.
  4. not home first: of the candidate's spot turns, the share that end nearer home while nearer to none of her
     spots is at most HOME_SLACK above base's (Zhe's revision: "completely stop having her head back home unless
     home is actually one of those high density spots or she literally has no other good option"). Base has no
     pull to home at all, so this asks that the build goes home, against her spots, about as rarely as a bot
     without the rule does.
passed = all four.
What changed from the attempt-2 check, and why: the build changed (Zhe's revision after the outcome test), so the
two targets of attempt 2 (home and one spot, the nearer first) are gone. The fall-back gate is now about the picked
spot only, and a new gate watches that home does not win against her spots. Home turns are counted apart as last
resort and are reported, not gated: how often she has no spot left is a fact about the idea, not about the build.
The thresholds were written before this file was run on any replay. It was then run once on attempt 2's replays
(the old build, and the same base games) to find bugs in the counting. ONE GATE WAS CHANGED AFTER THAT RUN, before
any switch-on game of this build existed: gate 4 was first written as "not above base's share". The run showed
base's share is 4% (5 of 115 spot turns), where one or two turns decide the gate either way, so it became "at most
0.05 above base's". The same run showed attempt 2's build at 16% on that row and 62% against base's 48% on gate 3;
both numbers were seen before the 0.05 was chosen. Gates 1 to 3 are as first written.
Reported, not part of the verdict: how many outnumbered turns are spot turns, last resort or holding; the split by
rebuilt "way open"; how spells end (a teammate back in view, or the enemy gone); spots dropped on arrival; the
same rows as attempts 1 and 2 (keep-away, first outnumbered turn of each pair, rule on-and-off, queen alive at
round 100 and 150, how she died, her length and pearls, team pearls, time near home, wins, timeouts); and the two
counts jun asked for: the change in steps on foot to the nearest teammate head on outnumbered turns, and how many
of her turns pass from her first outnumbered turn until a teammate's head is within MATE_NEAR steps on foot.
"""
import argparse, concurrent.futures as cf, glob, hashlib, json, os, statistics, sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# PASS RULE (fixed before any switch-on game of this build was played)
MIN_OUT_TURNS = 40     # outnumbered queen turns base must show over the whole run
MIN_GAME_SHARE = 0.5   # share of base games with at least one outnumbered queen turn
MIN_SPOT_TURNS = 30    # candidate spot turns needed to judge the fall-back
SPOT_SHARE = 0.50      # candidate: share of spot turns that end nearer to the picked spot ("most")
SPOT_GAIN = 0.15       # ... and that share minus base's
HOME_SLACK = 0.05      # candidate's home-against-spots share may be this much above base's (see the note above)

# The bot's settings this check mirrors (mybot2/main.cpp).
VIEW = 3               # VISION_RADIUS
GHOST = 3              # GHOST_ROUNDS: an enemy head counts for this many rounds after she last saw it
MEMORY = 40            # QF_MEMORY
HOLD = 2               # QF_HOLD
SPOTS = 4              # QF_SPOTS
MERGE = 6              # QF_MERGE
CROWD = 3              # QF_CROWD
GUARD_RADIUS = 5       # QF_GUARD_RADIUS, reported only
PAY_REACH = 3          # QS_PAY_REACH
KEEP = 2               # shortest a dragon can get by paying length

LAST_TURNS = 3         # "outnumbered before she died" looks at her last this-many turns
FLIP_GAP = 3           # the rule coming back on within this many of her turns counts as off-and-on
HOME_NEAR = 6          # "near home" = this many steps on foot or fewer
HOME_FROM = 60         # time near home is counted from this round
MATE_NEAR = 3          # "a teammate is near" = its head this many steps on foot or fewer from hers
REASONS = ['wall', 'self', 'body', 'head-on', 'no action']
SPOT_CLASSES = ('first_open', 'next_open', 'shut')
HOME_CLASSES = ('home_open', 'home_shut')
BUILT_AS = (
    "How attempt 3 is built (switch QUEEN_FALLBACK, off by default; Zhe's revision of 8 Oct on top of attempt 2). "
    "Unchanged from attempt 2: each turn the queen counts heads, ours are herself plus teammates' heads in her 7x7 "
    "view, theirs are enemy heads in view plus those she saw in the last 3 rounds; theirs >= ours is outnumbered "
    "(a draw counts) and the rule is on exactly on those turns. With a way open, the pull to the target leads "
    "(30000 points per step gained on foot, above keep-away, pearls and room); with every way shut, keep-away "
    "leads (1500 points per tile inside 5 tiles of an enemy head) and a 300-point pull breaks ties. Her existing "
    "safety stays above the pull (tiles an enemy head can reach this turn, dead ends, short-of-room steps). The "
    "opening centre pull, card 51's pull to unseen tiles and the barren-area route are off for her while the rule "
    "is on. What changed: (a) she now remembers up to 4 company spots instead of one, each with its margin (our "
    "heads minus theirs on the turn she saw it, herself counted), each kept 40 rounds; (b) while outnumbered her "
    "target is a company spot and never home as long as she has one she can walk to; (c) home is the target only "
    "when no spot is left (none seen in the last 40 rounds, or all dropped), and within 2 steps of home she "
    "holds as before. Builder's readings, say if wrong: 'where her teammates actually had advantages in number' "
    "is read as a turn with a teammate's head in view and more of ours than theirs, herself counted (so she and "
    "one teammate against one enemy head makes a spot), and the spot is the tile of the nearest teammate's head, "
    "as in attempt 2. 'High density' is read as the margin: spots are ranked by steps on foot and every head of "
    "margin above 1 counts as 3 steps nearer, so a bigger group beats a slightly nearer single teammate; nobody "
    "asked for the number 3. A new sighting within 6 tiles of a remembered spot replaces it (same place, newer "
    "news), and with 4 already remembered the oldest goes. Outnumbered within 2 steps on foot of a spot, that "
    "spot is dropped (she is there and has no upper hand) and the next one is tried. If the way to the first "
    "spot is shut the next spot in the order is tried; if every way is shut she keeps away this turn and does "
    "not turn to home. 'No other good option' is read as no spot left; home is then the target however far it "
    "is. A spot at or near home is simply a spot, so 'home is one of those spots' needs no extra rule. Not "
    "touched because the revision did not ask: lengths are still ignored in the count, the rule still goes off "
    "the moment a teammate is back in view, and teammates do nothing new.")


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
        'spot_turns', 'spot_nearer', 'spot_farther', 'spot_any', 'spot_home_only', 'spot_home_nearer',
        'spot_steps_sum', 'spot_margin_sum', 'spot_count_sum', 'spot_not_nearest',
        'mem_spot_turns', 'mem_spot_nearer', 'spots_made', 'spots_dropped',
        'last_turns', 'last_nearer', 'last_steps_sum', 'hold_turns', 'hold_kept', 'no_target_turns',
        'home_turns', 'home_nearer',
        'mate_turns', 'mate_nearer', 'mate_farther', 'mate_start_sum', 'mate_change_sum',
        'died_on_out_turn', 'episodes', 'restarts', 'ended_spells', 'ended_with_company',
        'late_turns', 'late_near_home', 'pearls_100', 'q_pearls_100', 'q_pearls', 'tle', 'points_max')}
    for c in SPOT_CLASSES + HOME_CLASSES:
        stat[f'{c}_turns'] = stat[f'{c}_ok'] = 0
    seen = {}              # enemy id -> last round its head was in her view
    spots = []             # [tile, margin, round], oldest first
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
        home_nearer = to_home[start] >= 1 and 0 <= to_home[end] < to_home[start]
        cls = p['cls']
        if cls in SPOT_CLASSES:
            pick = p['pick']
            nearer = 0 <= pick[end] < pick[start]
            any_spot = any(0 <= f[end] < f[start] for f in p['fields'])
            p.update(nearer=nearer)
            stat['spot_turns'] += 1
            stat['spot_nearer'] += nearer
            stat['spot_farther'] += pick[end] < 0 or pick[end] > pick[start]
            stat['spot_any'] += any_spot
            stat['spot_home_only'] += home_nearer and not any_spot
            stat['spot_home_nearer'] += home_nearer
            stat['spot_steps_sum'] += pick[start]
            stat['spot_margin_sum'] += p['margin']
            stat['spot_count_sum'] += len(p['fields'])
            stat['spot_not_nearest'] += pick[start] > min(f[start] for f in p['fields'])
            if not p['foes']:
                stat['mem_spot_turns'] += 1
                stat['mem_spot_nearer'] += nearer
            stat[f'{cls}_turns'] += 1
            stat[f'{cls}_ok'] += bool(p.get('away')) if cls == 'shut' else nearer
        elif cls == 'hold':
            stat['hold_turns'] += 1
            stat['hold_kept'] += 0 <= to_home[end] <= HOLD
        elif cls in HOME_CLASSES:
            p.update(nearer=home_nearer)
            stat['last_turns'] += 1
            stat['last_nearer'] += home_nearer
            stat['last_steps_sum'] += to_home[start]
            stat[f'{cls}_turns'] += 1
            stat[f'{cls}_ok'] += bool(p.get('away')) if cls == 'home_shut' else home_nearer
        else:
            stat['no_target_turns'] += 1
        if to_home[start] >= 1:
            stat['home_turns'] += 1
            stat['home_nearer'] += home_nearer
        mates = p['mates']
        if mates is not None and mates[start] >= 0 and mates[end] >= 0:
            stat['mate_turns'] += 1
            stat['mate_nearer'] += mates[end] < mates[start]
            stat['mate_farther'] += mates[end] > mates[start]
            stat['mate_start_sum'] += mates[start]
            stat['mate_change_sum'] += mates[end] - mates[start]

    def queen_turn():
        nonlocal pend, first, first_out, was_out, since_off, waited, mate_after
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
        spots[:] = [s for s in spots if rnd - s[2] <= MEMORY]
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
                # The nearest teammate's head is remembered with the margin; a sighting close to a spot replaces it.
                tile = min(friends, key=lambda f: (board.far(head, f), f))
                spots[:] = [s for s in spots if board.far(s[0], tile) > MERGE]
                if len(spots) >= SPOTS:
                    spots.pop(0)
                spots.append([tile, 1 + len(friends) - theirs, rnd])
                stat['spots_made'] += 1
            if was_out:
                since_off = 0
                stat['ended_spells'] += 1
                stat['ended_with_company'] += bool(friends)
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
        # Outnumbered within HOLD steps of a spot: it is dropped.
        kept = [s for s in spots if not 0 <= board.walk(s[0])[head] <= HOLD]
        stat['spots_dropped'] += len(spots) - len(kept)
        spots[:] = kept
        # Spots she can walk to, by steps on foot with CROWD steps off per head of margin above 1; newer on a tie.
        order = sorted((board.walk(s[0])[head] - CROWD * (s[1] - 1), board.walk(s[0])[head], -k)
                       for k, s in enumerate(spots) if board.walk(s[0])[head] >= 0)
        fields = [board.walk(spots[-k][0]) for _, _, k in order]

        def way(field):
            for d in range(4):
                n = board.nb[head][d]
                if board.side[head][d] == 0 and n not in taken and n not in danger and 0 <= field[n] < field[head]:
                    return True
            return False

        pick = margin = None
        home_d = to_home[head]
        if fields:
            lead = next((i for i, f in enumerate(fields) if way(f)), None)
            cls = 'shut' if lead is None else 'first_open' if lead == 0 else 'next_open'
            pick = fields[lead or 0]
            margin = spots[-order[lead or 0][2]][1]
        elif home_d < 0:
            cls = None
        elif home_d <= HOLD:
            cls = 'hold'
        else:
            cls = 'home_open' if way(to_home) else 'home_shut'
        pend = {'round': rnd, 'start': head, 'foes': foes, 'friends': len(friends), 'cls': cls, 'pick': pick,
                'fields': fields, 'margin': margin, 'mates': board.spread(mates) if mates else None}
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
        first = {'enemy_heads_in_view': len(first['foes']), 'spots': len(first['fields']),
                 **{k: first.get(k) for k in ('round', 'start', 'end', 'friends', 'cls', 'away', 'closer', 'nearer',
                                              'died')}}
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

    def share(group, top, bottom, digits=3):
        return {t: ratio(total(group, t, top), total(group, t, bottom), digits) for t in tags}

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
            'spot_turns': both(group, 'spot_turns'),
            'spot_turns_share_of_outnumbered_turns': share(group, 'spot_turns', 'out_done'),
            'ends_nearer_the_picked_spot': both(group, 'spot_nearer'),
            'ends_nearer_the_picked_spot_share': share(group, 'spot_nearer', 'spot_turns'),
            'ends_farther_from_the_picked_spot_share': share(group, 'spot_farther', 'spot_turns'),
            'ends_nearer_any_of_her_spots_share': share(group, 'spot_any', 'spot_turns'),
            'ends_nearer_home_and_none_of_her_spots': both(group, 'spot_home_only'),
            'ends_nearer_home_and_none_of_her_spots_share': share(group, 'spot_home_only', 'spot_turns'),
            'spot_turns_that_end_nearer_home_share': share(group, 'spot_home_nearer', 'spot_turns'),
            'picked_spot_steps_at_turn_start_mean': share(group, 'spot_steps_sum', 'spot_turns', 2),
            'picked_spot_margin_mean': share(group, 'spot_margin_sum', 'spot_turns', 2),
            'spots_remembered_on_a_spot_turn_mean': share(group, 'spot_count_sum', 'spot_turns', 2),
            'picked_spot_is_not_the_nearest_one': both(group, 'spot_not_nearest'),
            'way_open_to_first_spot_turns': both(group, 'first_open_turns'),
            'way_open_to_first_spot_ends_nearer_it_share': share(group, 'first_open_ok', 'first_open_turns'),
            'way_open_to_a_later_spot_only_turns': both(group, 'next_open_turns'),
            'way_open_to_a_later_spot_only_ends_nearer_it_share': share(group, 'next_open_ok', 'next_open_turns'),
            'every_way_shut_turns': both(group, 'shut_turns'),
            'every_way_shut_ends_farther_from_enemy_share': share(group, 'shut_ok', 'shut_turns'),
            'no_enemy_in_view_spot_turns': both(group, 'mem_spot_turns'),
            'no_enemy_in_view_ends_nearer_the_picked_spot_share': share(group, 'mem_spot_nearer', 'mem_spot_turns'),
            'spot_sightings': both(group, 'spots_made'),
            'spots_dropped_on_arrival': both(group, 'spots_dropped'),
            'last_resort_turns': both(group, 'last_turns'),
            'last_resort_share_of_outnumbered_turns': share(group, 'last_turns', 'out_done'),
            'last_resort_ends_nearer_home_share': share(group, 'last_nearer', 'last_turns'),
            'last_resort_steps_to_home_mean': share(group, 'last_steps_sum', 'last_turns', 2),
            'last_resort_way_open_turns': both(group, 'home_open_turns'),
            'last_resort_way_open_ends_nearer_home_share': share(group, 'home_open_ok', 'home_open_turns'),
            'last_resort_way_shut_turns': both(group, 'home_shut_turns'),
            'holding_turns': both(group, 'hold_turns'),
            'holding_ends_within_2_steps_of_home_share': share(group, 'hold_kept', 'hold_turns'),
            'turns_with_no_target_at_all': both(group, 'no_target_turns'),
            'ends_nearer_home_share': share(group, 'home_nearer', 'home_turns'),
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
            'nearest_teammate_steps_at_turn_start_mean': share(group, 'mate_start_sum', 'mate_turns', 2),
            'nearest_teammate_steps_change_per_turn_mean': share(group, 'mate_change_sum', 'mate_turns', 2),
            'turns_until_a_teammate_is_near': {t: wait(group, t) for t in tags},
            'rule_on_spells': both(group, 'episodes'),
            'spells_restarting_within_3_turns': both(group, 'restarts'),
            'spells_ended': both(group, 'ended_spells'),
            'spells_ended_with_a_teammate_in_view': both(group, 'ended_with_company'),
            'first_turn_pairs_same_position': len(firsts),
            'first_turn_moves_differ': len(differ),
            'first_turn_ends_farther': {t: first_count(firsts, t, 'away') for t in tags},
            'first_turn_ends_nearer_enemy': {t: first_count(firsts, t, 'closer') for t in tags},
            'first_turn_ends_nearer_its_target': {t: first_count(firsts, t, 'nearer') for t in tags},
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
    spot = w['ends_nearer_the_picked_spot_share']
    homeward = w['ends_nearer_home_and_none_of_her_spots_share']
    target_seen = (w['outnumbered_turns']['base'] >= MIN_OUT_TURNS and
                   w['games_with_an_outnumbered_turn']['base'] >= MIN_GAME_SHARE * n and
                   w['spot_turns']['candidate'] >= MIN_SPOT_TURNS)
    checks = {
        'target_seen': target_seen,
        'nothing_else_changes': silent == n,
        'goes_to_company': (target_seen and spot['candidate'] is not None and spot['candidate'] >= SPOT_SHARE and
                            (spot['base'] is None or spot['candidate'] - spot['base'] >= SPOT_GAIN - 1e-9)),
        'not_home_first': (target_seen and homeward['candidate'] is not None and homeward['base'] is not None and
                           homeward['candidate'] <= homeward['base'] + HOME_SLACK + 1e-9),
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
        f"{'PASS' if passed else 'FAIL'} ({'all four checks' if passed else 'failed: ' + ', '.join(failed)}). "
        f"{n} paired games on {len(by_map)} maps, base -> candidate throughout. Outnumbered queen turns "
        f"{two(w['outnumbered_turns'])} ({two(w['outnumbered_share_of_queen_turns'], pct)} of her turns; in "
        f"{two(w['games_with_an_outnumbered_turn'])} games; no teammate in view on "
        f"{two(w['outnumbered_turns_with_no_teammate_in_view'])}; no enemy head in view any more on "
        f"{two(w['outnumbered_with_no_enemy_head_in_view'])}). Spot turns (she has a company spot to walk to) "
        f"{two(w['spot_turns'])}, that is {two(w['spot_turns_share_of_outnumbered_turns'], pct)} of her outnumbered "
        f"turns; last resort (no spot, home is the target) {two(w['last_resort_turns'])}; holding within {HOLD} "
        f"steps of home {two(w['holding_turns'])}. Goes to company: on spot turns she ends nearer to the picked "
        f"spot on {two(spot, pct)} (gate: {SPOT_SHARE:.2f} and +{SPOT_GAIN:.2f} over base), farther from it on "
        f"{two(w['ends_farther_from_the_picked_spot_share'], pct)}, nearer to any of her spots on "
        f"{two(w['ends_nearer_any_of_her_spots_share'], pct)}. Not home first: on spot turns she ends nearer home "
        f"and nearer none of her spots on {two(homeward, pct)} (gate: at most +{HOME_SLACK:.2f} over base); spot "
        f"turns that end nearer "
        f"home at all {two(w['spot_turns_that_end_nearer_home_share'], pct)}; all outnumbered turns that end nearer "
        f"home {two(w['ends_nearer_home_share'], pct)}. The picked spot is "
        f"{two(w['picked_spot_steps_at_turn_start_mean'])} steps away on average, margin "
        f"{two(w['picked_spot_margin_mean'])}, with {two(w['spots_remembered_on_a_spot_turn_mean'])} spots "
        f"remembered; it is not the nearest one on {two(w['picked_spot_is_not_the_nearest_one'])} turns. Rebuilt "
        f"split: way open to the first spot {two(w['way_open_to_first_spot_turns'])} turns, ends nearer it "
        f"{two(w['way_open_to_first_spot_ends_nearer_it_share'], pct)}; open to a later spot only "
        f"{two(w['way_open_to_a_later_spot_only_turns'])} turns, ends nearer it "
        f"{two(w['way_open_to_a_later_spot_only_ends_nearer_it_share'], pct)}; every way shut "
        f"{two(w['every_way_shut_turns'])} turns, ends farther from the nearest enemy head "
        f"{two(w['every_way_shut_ends_farther_from_enemy_share'], pct)}. Last resort: home is "
        f"{two(w['last_resort_steps_to_home_mean'])} steps away on average and she ends nearer it on "
        f"{two(w['last_resort_ends_nearer_home_share'], pct)}; holding turns that stay within {HOLD} steps "
        f"{two(w['holding_ends_within_2_steps_of_home_share'], pct)}. Spots dropped on arrival (there and still "
        f"outnumbered) {two(w['spots_dropped_on_arrival'])}; spells that ended with a teammate back in view "
        f"{two(w['spells_ended_with_a_teammate_in_view'])} of {two(w['spells_ended'])}. Keep-away (a tie-break, "
        f"turns with an enemy head in view): ends farther from the nearest enemy head "
        f"{two(w['ends_farther_share'], pct)}, nearer {two(w['ends_nearer_share'], pct)}, next to one "
        f"{two(w['ends_next_to_an_enemy_head'])}. Nearest teammate head on outnumbered turns "
        f"({two(w['nearest_teammate_turns_measured'])} turns): "
        f"{two(w['nearest_teammate_steps_at_turn_start_mean'])} steps on foot at the start of the turn, change "
        f"per turn {two(w['nearest_teammate_steps_change_per_turn_mean'])}, ends nearer "
        f"{two(w['nearest_teammate_ends_nearer_share'], pct)}, farther "
        f"{two(w['nearest_teammate_ends_farther_share'], pct)}. Her turns from her first outnumbered turn until a "
        f"teammate's head is within {MATE_NEAR} steps: base {waited(wt['base'])}; candidate "
        f"{waited(wt['candidate'])}. First outnumbered turn of a pair, same position in both games: "
        f"{w['first_turn_pairs_same_position']} pairs, moves differ in {w['first_turn_moves_differ']}; ends nearer "
        f"its target {two(w['first_turn_ends_nearer_its_target'])}, farther from the enemy "
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
                       'MIN_SPOT_TURNS': MIN_SPOT_TURNS, 'SPOT_SHARE': SPOT_SHARE, 'SPOT_GAIN': SPOT_GAIN,
                       'HOME_SLACK': HOME_SLACK, 'VIEW': VIEW, 'GHOST': GHOST, 'MEMORY': MEMORY, 'HOLD': HOLD, 'SPOTS': SPOTS, 'MERGE': MERGE,
                       'CROWD': CROWD, 'GUARD_RADIUS': GUARD_RADIUS, 'PAY_REACH': PAY_REACH,
                       'LAST_TURNS': LAST_TURNS, 'FLIP_GAP': FLIP_GAP, 'HOME_NEAR': HOME_NEAR,
                       'HOME_FROM': HOME_FROM, 'MATE_NEAR': MATE_NEAR},
        'built_as': BUILT_AS,
        'games': n,
        'pairs_same_until_first_outnumbered_turn': silent,
        'all_games': w,
        'by_map': by_map,
        'limits': 'Outnumbered, the company spots and the picked spot are rebuilt from head positions in the replay, '
                  'not read from the bot. The rebuild walks the real walls; the bot walks the walls it has seen and '
                  'treats unseen sides as open, so the ranking of spots and the picked one can differ on a few '
                  'turns. "Way open" is the roughest part: it uses each enemy dragon\'s true length where the bot '
                  'uses the parts it has seen, and it does not rebuild her dead-end, room and exposure rules, which '
                  'may still forbid the step; the gate on the picked spot leans on it only to choose between spots. '
                  'A turn that ends nearer a tile is something a dragon moving at random also does fairly often, so '
                  'read every share against base. After the first outnumbered turn the two games of a pair are '
                  'different games, so the shares compare two sets of positions; only the first-turn rows compare '
                  'the same position. A turn on which she died is in no "ends" share. A spot says where a teammate '
                  'stood up to 40 rounds ago; the check does not know whether anyone is still there, and the '
                  '"spells ended with a teammate in view" and nearest-teammate rows are the only ones that look at '
                  'that. Nearest teammate is on foot over the whole map, wherever the teammate is. The local '
                  'opponent is our own release. Four games a map: deaths, lengths and pearls are small counts and '
                  'no verdict on outcomes.',
        'pairs': pairs,
    }
    with open(a.output, 'w') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print(note)


if __name__ == '__main__':
    main()
