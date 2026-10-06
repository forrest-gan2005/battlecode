#!/usr/bin/env python3
"""Card #38 queen-loop mechanism check (QUEEN_LOOP, second build): does our queen circle a 2x2 square for the whole
game when no pearl is close, does she step off when an enemy head comes near, and does the team stop feeding her and
feed its longest other dragon?

usage: python3 work/card_38_check.py --replays DIR --base base --candidate candidate --output FILE
Replays are DIR/<tag>_<map>_<seed>_<side>.replay (work/ab3.py with KEEP=1), paired by (map, seed, side).

Everything is rebuilt from the replay alone; the game runner drops the bot's own log lines.

  decision   = one action of our queen (dragon 0 or 1 on our side). She acts once a round.
  early / late = before round LATE / from round LATE on. LATE is r300: the first build stopped looping there, and it
               is where the release bot starts feeding a living queen on maps over 600 tiles.
  lap step   = a one-tile move that brings her head back to where it was four actions ago, the four tiles in between
               forming a 2x2 square, each of those four actions a one-tile move. So the first three steps of a loop
               are not lap steps (they cannot be told from walking); every step after that is.
  loop       = a run of lap steps in a row, plus the three steps before it ("lead-in").
  loop share = lap steps / her decisions, over the whole game (also given early and late).
  steady loop = a loop of at least STEADY lap steps in a row (two more full laps after the first). The bot without
               the switch also walks a lap now and then, and circles inside a closed-off home; those are counted the
               same way on both sides.
  on the loop = a decision right after a lap step, 2-3 long, on a square more than HOME_CLEAR tiles from her spawn
               tile (only there can the new rule be the one moving her). Her square is the four tiles of that lap;
               "going on" = her next action is a one-tile move to the next tile of the square in the same direction.
  view       = the 7x7 box around her head. Only what is in it counts as seen.
  reach      = how far an enemy head can come in one turn: free steps (ceil(length / 4)) plus one step per length
               it can pay down to 2. Length = the most parts of it she saw in the last 3 rounds; a body that runs
               out of her view counts as one longer, and at least 3. A head not seen for 1-3 rounds keeps its last
               tile and gets 1 more reach per round unseen.
  margin     = walking distance from an enemy head to a tile (kelp walls and portals walked, other dragons' bodies
               in view block) minus that head's reach. "tight" = some tile of her square has margin below MARGIN.
  true tight = the same with the real length of every enemy head in view (the replay knows it, she does not).
  pushed off = on the loop, tight, and she did not go on. The heads that made it tight are remembered with the tile
               and round she last saw them.
  near a pusher = a lap step on a square with a tile within AWAY_TILES of such a head's last seen tile, less than
               AWAY_ROUNDS rounds after she last saw it.
  quiet      = a decision with her 2-3 long, more than HOME_CLEAR tiles from her spawn tile, no enemy head seen in
               the last 3 rounds, and no pearl in view within PEARL_STEPS walking steps. This is the situation the
               card is about; it is counted the same way with the switch off and on, in every round.
  tiles per 100 = different tiles her head stood on, per 100 decisions.
  feed death = one of our dragons other than the queen ending its own turn with the "die" action (the replay's
               suicide action; the engine records the death as "no valid action"). This is how the bot feeds.
  feed pearl = a pearl that appears on a tile of such a dragon's body in the round it dies, counted until it is
               eaten or gone. A dead dragon leaves a pearl on every other tile of its body, head first.
  lead       = our longest dragon other than the queen at that moment (the replay cannot show which dragon the bot
               itself calls its leader; with the switch on the bot's leader is the longest other dragon it knows of).
  feed death by the queen / by the lead = within FEED_NEAR tiles of that head, the closer of the two; the bot drops
               feeders up to 8 tiles ahead of the leader and one to the side.

PASS RULE (fixed before any switch-on game of this build was played; the constants are below):
  1. target seen: with the switch off she has at least QUIET_MIN quiet decisions, she is alive at round LATE in at
     least LATE_ALIVE_MIN games, and she eats at least BASE_FEED_MIN feed pearls (so there is a late game and a fed
     queen for the change to act on);
  2. she loops: switch-on loop share is at least LOOP_SHARE_MIN, and at least LOOP_SHARE_GAIN above switch-off;
  3. she roams less: switch-on tiles per 100 is below switch-off;
  4. she keeps circling late: with the switch on she has at least LATE_N late quiet decisions, and at least
     LATE_QUIET_LAPS of them are lap steps. Fewer than LATE_N fails the check: then the run did not show it;
  5. nobody feeds her: with the switch on our team eats at least FEED_N feed pearls while she is alive, and she
     eats at most QUEEN_FEED_MAX of them. Fewer than FEED_N fails the check: then the run did not show it;
  6. she steps off, judged only if it comes up: with at least TIGHT_N switch-on decisions on the loop that are
     tight, she goes on in at most TIGHT_STAY of them. When it is tight the new rule lets go and the normal move
     rules pick her step; they can pick the next tile of the square by themselves, so this is not expected to be
     zero. A loop that never let go would go on nearly every time;
  7. she stays away, judged only if it comes up: with at least PUSH_N switch-on push-offs, at most NEAR_MAX of them
     are followed by a lap step near that pusher (the normal move rules can walk a lap there by themselves);
  8. the square is where the card says, judged only with at least PLACE_N switch-on lap steps in steady loops: at
     most PLACE_BAD of them more than switch-off's own count are within HOME_CLEAR tiles of her spawn tile, the
     same for a portal on or beside the square, and the same for steps taken 4 or longer.
Rules 6-8 report "not seen" below their minimum and do not fail the check then.
Deaths, rams, lengths, how games ended and wins are raw numbers and NOT part of the pass rule: 16 games per side
cannot settle them, the outcome A/B does.
"""
import argparse, glob, hashlib, json, os, sys, concurrent.futures as cf
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import replay

# PASS RULE (fixed before any switch-on game of this build)
QUIET_MIN = 100        # switch-off quiet decisions needed to call the target seen
LATE_ALIVE_MIN = 2     # switch-off games with our queen alive at round LATE needed to call the target seen
BASE_FEED_MIN = 20     # switch-off feed pearls eaten by our queen needed to call the target seen
LOOP_SHARE_MIN = 0.10  # switch-on lap steps per decision (the card's "10%+")
LOOP_SHARE_GAIN = 0.08 # and at least this much above switch-off
LATE_N = 100           # switch-on late quiet decisions needed to judge the late loop
LATE_QUIET_LAPS = 0.50 # share of those that must be lap steps
FEED_N = 20            # switch-on feed pearls eaten by our team while she is alive, needed to judge feeding
QUEEN_FEED_MAX = 0.10  # share of those she may eat
TIGHT_N = 10           # switch-on tight decisions on the loop needed to judge stepping off
TIGHT_STAY = 0.70      # share of those where she may go on (the normal move rules pick the same tile now and then)
PUSH_N = 5             # switch-on push-offs needed to judge staying away
NEAR_MAX = 0.30        # share of push-offs that may be followed by a lap step near the pusher
PLACE_N = 20           # switch-on lap steps in steady loops needed to judge where the square is
PLACE_BAD = 0.02       # share of those, beyond switch-off's own count, that may break each placement rule
STEADY = 8             # lap steps in a row that make a steady loop

# The bot's constants (mybot2/main.cpp)
LATE = 300             # QUEEN_GAME_FEED_ROUND, and the first build's last loop round
MAX_LEN = 3            # QL_MAX_LENGTH
MARGIN = 2             # QL_MARGIN: she steps off below this
PEARL_STEPS = 4        # QL_PEARL_STEPS
HOME_CLEAR = 4         # QL_HOME_CLEAR
AWAY_TILES = 4         # QL_AWAY_TILES
AWAY_ROUNDS = 8        # QL_AWAY_ROUNDS
FEED_NEAR = 9          # FEEDER_DROP_MAX + 1: the farthest a feeder dies from the leader's head
VIEW = 3               # the bot sees a 7x7 box around its head
GHOST_ROUNDS = 3       # how long the bot remembers an enemy head
FREE_DIV = 4           # free steps per turn = ceil(length / 4)
MIN_SIZE = 2           # a dragon cannot pay itself below this
START_SIZE = 3         # INITIAL_LENGTH: the least a half-hidden enemy is taken to be
CAUSE = ['wall', 'self', 'body', 'headon', 'none']
DIRS = 'NESW'
MARKS = (100, 200, 300, 400)


def load_map(text):
    """Returns W, H, step(cell, d) -> (next cell, through a portal) or None for kelp / an unpaired portal, and
    gate(cell) -> True if one of the tile's four edges is a portal."""
    lines = text.splitlines()
    W, H = map(int, lines[0].split()[1:3])
    S = 2 * (W + 1)
    kind, pid_of, members = {}, {}, {}
    for l in lines:
        q = l.split()
        if not q or q[0] != 'EDGE':
            continue
        i, t = int(q[1]), int(q[2])
        if t == 0:
            continue
        y, r = divmod(i, S)
        if r < W + 1:
            if r == W:
                continue
            key = ('N', r, y % H)
        else:
            if y >= H:
                continue
            key = ('W', (r - (W + 1)) % W, y)
        if t >= kind.get(key, 0):
            kind[key] = t
            if t == 2 and len(q) > 3:
                pid_of[key] = int(q[3])
    for key, pid in pid_of.items():
        if kind.get(key) == 2:
            members.setdefault(pid, []).append(key)
    pair = {}
    for keys in members.values():
        if len(keys) == 2 and keys[0][0] == keys[1][0]:
            pair[keys[0]], pair[keys[1]] = keys[1], keys[0]

    def edge(cell, d):
        x, y = cell
        if d == 'N':
            return ('N', x, y), (x, (y - 1) % H)
        if d == 'S':
            return ('N', x, (y + 1) % H), (x, (y + 1) % H)
        if d == 'W':
            return ('W', x, y), ((x - 1) % W, y)
        return ('W', (x + 1) % W, y), ((x + 1) % W, y)

    def step(cell, d):
        key, straight = edge(cell, d)
        t = kind.get(key, 0)
        if t == 0:
            return straight, False
        other = pair.get(key) if t == 2 else None
        if other is None:
            return None
        _, bx, by = other
        if d == 'N':
            return (bx, (by - 1) % H), True
        if d == 'W':
            return ((bx - 1) % W, by), True
        return (bx, by), True

    def gate(cell):
        return any(kind.get(edge(cell, d)[0], 0) == 2 for d in DIRS)

    return W, H, step, gate


def gap(a, b, size):
    raw = abs(a - b)
    return min(raw, size - raw)


def full_reach(size):
    """Free plus paid steps of a dragon this long."""
    size = max(size, MIN_SIZE)
    return (size + FREE_DIV - 1) // FREE_DIV + size - MIN_SIZE


def margins(step, foes, key, blocked, own):
    """Lowest (walking distance - reach) per tile over `foes`, for tiles below MARGIN + 1; and which foe is lowest.
    Her own tiles are measured but not walked through, as in the bot."""
    low = {}
    for foe in foes:
        reach = foe[key]
        if reach is None:
            continue
        seen = {foe['at']}
        frontier = [foe['at']]
        for n in range(reach + MARGIN):
            nxt = []
            for cell in frontier:
                for d in DIRS:
                    hop = step(cell, d)
                    if hop is None:
                        continue
                    to = hop[0]
                    if to in seen or to in blocked:
                        continue
                    seen.add(to)
                    value = n + 1 - reach
                    if to not in low or value < low[to][0]:
                        low[to] = (value, foe['id'])
                    if to not in own:
                        nxt.append(to)
            frontier = nxt
    return low


def square_of(cells, W, H):
    """The four tiles as a 2x2 square, or None."""
    cells = set(cells)
    xs, ys = sorted({c[0] for c in cells}), sorted({c[1] for c in cells})
    if len(cells) != 4 or len(xs) != 2 or len(ys) != 2 or gap(xs[0], xs[1], W) != 1 or gap(ys[0], ys[1], H) != 1:
        return None
    return cells if cells == {(x, y) for x in xs for y in ys} else None


def one(job):
    path, side = job
    ours = 'A' if side == '0' else 'B'
    root = replay.load(path).root()
    text = root.text(0)
    W, H, step, gate = load_map(text)
    result = root.pointer(4)
    winner = ('A', 'B')[result.u16(6)] if result.u16(4) == 1 else None
    bodies, team_of = {}, {}
    for line in text.splitlines():
        q = line.split()
        if q and q[0] == 'DRAGON':
            did = len(bodies)
            bodies[did] = deque((int(q[3 + 2 * k]), int(q[4 + 2 * k])) for k in range(int(q[2])))
            team_of[did] = 'A' if int(q[1]) == 0 else 'B'
    queen = next((i for i in (0, 1) if team_of.get(i) == ours), None)
    c = Counter(games=1, win=int(winner == ours))
    track = hashlib.sha1()
    if queen is None:
        raise ValueError(f'{path}: no queen on our side')
    spawn = bodies[queen][0]

    def far(a, b):
        return gap(a[0], b[0], W) + gap(a[1], b[1], H)

    pearls = set()
    memory = {}          # enemy id -> (round last seen, parts, tile)
    pushers = {}         # enemy id -> [tile, round last seen, True once a lap step came near]
    trail = [spawn]      # her head after each action
    single = []          # was that action a one-tile move
    lap = []             # was that action a lap step
    rounds = []          # round of each action
    stood = set()
    stood_early = set()
    run = Counter()      # the loop she is on: lap steps, and how many of them break a placement rule
    corpse = {}          # tile of a feeder's body -> round it died
    feed_pearl = set()   # tiles holding a feed pearl
    taken = {}           # tile -> round a feed pearl was picked up from it
    pending = None
    mover = None
    rnd = 0
    alive = True

    def lead_of(skip=None):
        """Our longest dragon other than the queen (and other than `skip`), or None."""
        best = None
        for did, b in bodies.items():
            if b and did != queen and did != skip and team_of.get(did) == ours and (best is None or len(b) > len(bodies[best])):
                best = did
        return best

    def look():
        body = bodies[queen]
        head = body[0]

        def in_view(cell):
            return gap(cell[0], head[0], W) <= VIEW and gap(cell[1], head[1], H) <= VIEW

        def on_edge(cell):
            return gap(cell[0], head[0], W) == VIEW or gap(cell[1], head[1], H) == VIEW

        own = set(body)
        own.discard(body[-1])
        others, foes = set(), []
        for did, b in bodies.items():
            if did == queen or not b:
                continue
            inside = [cell for cell in b if in_view(cell)]
            others.update(inside)
            if team_of.get(did) == ours or not in_view(b[0]):
                continue
            was = memory.get(did)
            parts = max(len(inside), was[1]) if was and rnd - was[0] <= GHOST_ROUNDS else len(inside)
            memory[did] = (rnd, parts, b[0])
            cut = any(on_edge(cell) for cell in inside)
            size = max(parts, len(inside) + 1, START_SIZE) if cut else parts
            foes.append(dict(id=did, at=b[0], seen=rnd, reach=full_reach(size), true=full_reach(len(b))))
            if did in pushers:
                pushers[did][0], pushers[did][1] = b[0], rnd
        for did, (seen, parts, at) in memory.items():
            if seen != rnd and rnd - seen <= GHOST_ROUNDS:
                foes.append(dict(id=did, at=at, seen=seen, reach=full_reach(parts) + rnd - seen, true=None))
        for did in [d for d, p in pushers.items() if rnd - p[1] >= AWAY_ROUNDS]:
            del pushers[did]

        # A pearl in view within PEARL_STEPS walking steps, portals not taken.
        low = margins(step, foes, 'reach', others, own) if foes else {}
        pearl = safe_pearl = False
        seen = {head}
        frontier = [(head, True)]
        for n in range(PEARL_STEPS):
            nxt = []
            for cell, safe in frontier:
                for d in DIRS:
                    hop = step(cell, d)
                    if hop is None or hop[1]:
                        continue
                    to = hop[0]
                    if to in seen or to in others or to in own or not in_view(to):
                        continue
                    seen.add(to)
                    ok = safe and low.get(to, (MARGIN,))[0] >= MARGIN
                    if to in pearls:
                        pearl = True
                        safe_pearl = safe_pearl or ok
                    nxt.append((to, ok))
            frontier = nxt
        p = dict(rnd=rnd, start=head, end=head, len=len(body), n=0, seen=0, dead=False, cause=None,
                 foes=len(foes), pearl=pearl, safe_pearl=safe_pearl, on=False, other_lap=False,
                 quiet=(MIN_SIZE <= len(body) <= MAX_LEN and not foes and not pearl and far(head, spawn) > HOME_CLEAR))
        if lap and lap[-1]:
            cells = trail[-4:]
            p['other_lap'] = not (len(body) <= MAX_LEN and all(far(t, spawn) > HOME_CLEAR for t in cells))
        if lap and lap[-1] and not p['other_lap']:
            p['on'] = True
            p['square'] = cells
            p['expect'] = cells[0]
            p['blocked'] = cells[0] in others
            tight = [low[t] for t in cells if t in low and low[t][0] < MARGIN]
            p['tight'] = bool(tight)
            p['pushed_by'] = {foe['id']: (foe['at'], foe['seen']) for foe in foes if any(t[1] == foe['id'] for t in tight)}
            real = margins(step, foes, 'true', others, own) if foes else {}
            p['true_tight'] = any(t in real and real[t][0] < MARGIN for t in cells)
        return p

    def flush():
        if run['n'] >= STEADY:
            c['steady_loops'] += 1
            for name, value in run.items():
                c['steady_' + name] += value
        run.clear()

    def close():
        nonlocal pending
        p, pending = pending, None
        if p is None:
            return
        moved = p['kind'] == 'move' and not p['dead']
        one_step = moved and p['n'] == 1 and p['seen'] == 1
        trail.append(p['end'])
        single.append(one_step)
        rounds.append(p['rnd'])
        k = len(single) - 1
        cells = trail[-4:]
        is_lap = (k >= 3 and all(single[-4:]) and trail[-5] == trail[-1] and square_of(cells, W, H) is not None)
        lap.append(is_lap)
        track.update(f"{p['rnd']}{p['kind']}{p['end']}{p['dead']}".encode())
        when = '_early' if p['rnd'] < LATE else '_late'
        short = MIN_SIZE <= p['len'] <= MAX_LEN
        c['decisions'] += 1
        c['decisions' + when] += 1
        c['short'] += short
        c['short' + when] += short
        c['quiet'] += p['quiet']
        c['quiet' + when] += p['quiet']
        c['foe_seen'] += p['foes'] > 0
        c['pearl_near'] += p['pearl']
        c['moves'] += p['kind'] == 'move'
        c['queen_feed_deaths'] += p['kind'] == 'die'
        c['path_mismatch'] += p['kind'] == 'move' and not p['dead'] and p['seen'] != p['n']
        if not p['dead']:
            stood.add(p['end'])
            if p['rnd'] < LATE:
                stood_early.add(p['end'])
        if not is_lap:
            flush()
        else:
            beside = set(cells)
            for x, y in cells:
                beside.update(((x, (y - 1) % H), (x, (y + 1) % H), ((x - 1) % W, y), ((x + 1) % W, y)))
            flags = dict(n=1, home=any(far(t, spawn) <= HOME_CLEAR for t in cells), portal=any(gate(t) for t in beside),
                         long=p['len'] > MAX_LEN)
            for name, value in flags.items():
                run[name] += value
            c['lap_steps'] += 1
            c['lap_steps' + when] += 1
            c['lap_quiet'] += p['quiet']
            c['lap_quiet' + when] += p['quiet']
            c['lap_long'] += flags['long']
            c['lap_home'] += flags['home']
            c['lap_portal'] += flags['portal']
            c['lap_pearl'] += any(t in pearls for t in beside)
            for did, rec in pushers.items():
                if not rec[2] and any(far(t, rec[0]) <= AWAY_TILES for t in cells):
                    rec[2] = True
                    c['push_then_near'] += 1
            if not (k >= 1 and lap[-2]):
                c['loops'] += 1
                c['lead_in_steps'] += 3
        c['other_lap_decisions'] += p['other_lap']
        if p['on']:
            went_on = one_step and p['end'] == p['expect']
            c['on_loop'] += 1
            c['on_loop_went_on'] += went_on
            c['on_loop_tight'] += p['tight']
            c['on_loop_tight_went_on'] += p['tight'] and went_on
            c['on_loop_true_tight'] += p['true_tight']
            c['on_loop_true_tight_went_on'] += p['true_tight'] and went_on
            c['on_loop_true_tight_unseen'] += p['true_tight'] and not p['tight']
            if not went_on:
                why = ('tight' if p['tight'] else 'pearl' if p['safe_pearl'] else 'long' if p['len'] > MAX_LEN
                       else 'blocked' if p['blocked'] else 'foe_seen' if p['foes'] else 'other')
                c['left_' + why] += 1
                c['left_died'] += p['dead']
                if p['tight']:
                    c['push_offs'] += 1
                    for did, (at, seen) in p['pushed_by'].items():
                        pushers[did] = [at, seen, False]

    def feed_death(did):
        """One of our dragons other than the queen dies on purpose: where, and which tiles its pearls land on."""
        body = bodies[did]
        when = '_early' if rnd < LATE else '_late'
        c['feed_deaths'] += 1
        c['feed_deaths' + when] += 1
        for cell in body:
            corpse[cell] = rnd
        if not (alive and bodies.get(queen)):
            return
        c['feed_deaths_alive'] += 1
        lead = lead_of(did)
        to_queen = far(body[0], bodies[queen][0])
        to_lead = far(body[0], bodies[lead][0]) if lead is not None else None
        by_queen = to_queen <= FEED_NEAR and (to_lead is None or to_queen <= to_lead)
        by_lead = not by_queen and to_lead is not None and to_lead <= FEED_NEAR
        c['feed_deaths_by_queen'] += by_queen
        c['feed_deaths_by_lead'] += by_lead
        c['feed_deaths_elsewhere'] += not by_queen and not by_lead

    for ev in root.pointer(3):
        which = ev.u16(0)
        kind = replay.EVENT_NAMES[which] if which < len(replay.EVENT_NAMES) else ''
        pl = ev.pointer(0)
        if kind == 'roundStart':
            close()
            mover = None
            rnd = pl.i32(0)
            for mark in MARKS:
                if rnd == mark:
                    lead = lead_of()
                    c[f'games_r{mark}'] += 1
                    c[f'lead_len_sum_r{mark}'] += len(bodies[lead]) if lead is not None else 0
                    if alive and bodies.get(queen):
                        c[f'alive_r{mark}'] += 1
                        c[f'len_sum_r{mark}'] += len(bodies[queen])
        elif kind == 'tileChange':
            at = replay.point(pl.pointer(0))
            if pl.u32(0) == 1:
                pearls.add(at)
                if corpse.pop(at, -1) == rnd:
                    feed_pearl.add(at)
                    c['feed_pearls'] += 1
            else:
                pearls.discard(at)
                if at in feed_pearl:
                    feed_pearl.discard(at)
                    taken[at] = rnd
        elif kind == 'dragonAction':
            close()
            mover = pl.i32(0)
            a = pl.pointer(0)
            what = a.u16(0) if a is not None else 0
            if what == 2 and mover != queen and team_of.get(mover) == ours and bodies.get(mover):
                feed_death(mover)
            if mover != queen or a is None or not bodies.get(queen):
                continue
            pending = look()
            pending['kind'] = 'move' if what == 0 else 'split' if what == 1 else 'die' if what == 2 else 'other'
            try:
                pending['n'] = max(1, len(a.pointer(0))) if what == 0 else 0
            except Exception:
                pending['n'] = 1
        elif kind == 'dragonUpdate':
            did = pl.i32(0)
            h = replay.point(pl.pointer(0))
            tp = replay.point(pl.pointer(1))
            b = bodies.setdefault(did, deque())
            before = len(b)
            hopped = bool(b) and b[0] != h
            lead = lead_of() if hopped and taken.get(h) == rnd else None
            if not b or b[0] != h:
                if b:
                    c['hops'] += 1
                    c['hop_mismatch'] += all((step(b[0], d) or (None,))[0] != h for d in DIRS)
                b.appendleft(h)
                if pending and did == queen:
                    pending['seen'] += 1
                    pending['end'] = h
            while len(b) > 1 and b[-1] != tp:
                b.pop()
            # A step that leaves the dragon one longer ate a pearl.
            if hopped and len(b) > before:
                mine = team_of.get(did) == ours
                if mine:
                    c['team_eats_r50'] += rnd <= 50
                    c['team_eats_r100'] += rnd <= 100
                    c['queen_eats'] += did == queen
                    c['queen_eats_early' if rnd < LATE else 'queen_eats_late'] += did == queen
                if taken.get(h) == rnd:
                    del taken[h]
                    who = 'queen' if did == queen else 'lead' if did == lead else 'others' if mine else 'enemy'
                    c['feed_eaten_by_' + who] += 1
                    if mine and alive and bodies.get(queen):
                        c['feed_eaten_alive'] += 1
                        c['feed_eaten_alive_by_' + who] += 1
        elif kind == 'dragonSplit':
            pa, ch = pl.i32(0), pl.i32(4)
            bodies[pa] = deque(replay.point(x) for x in pl.pointer(0))
            bodies[ch] = deque(replay.point(x) for x in pl.pointer(1))
            team_of[pa] = team_of[ch] = ('A', 'B')[pl.u16(8)]
            c['queen_splits'] += pa == queen
        elif kind == 'dragonDeath':
            did = pl.i32(0)
            r = pl.u16(4)
            bodies.pop(did, None)
            if did != queen:
                continue
            cause = CAUSE[r] if r < 5 else 'other'
            alive = False
            if pending:
                pending['dead'] = True
                pending['cause'] = cause
            on_loop = bool(lap and lap[-1]) and not pending
            c['queen_deaths'] += 1
            c['queen_deaths_early'] += rnd < LATE
            c[f'queen_deaths_{cause}'] += 1
            c['queen_death_round_sum'] += rnd
            if cause == 'headon' and mover != queen:
                c['queen_rammed'] += 1
                c['queen_rammed_on_loop'] += on_loop
            elif cause == 'headon':
                c['queen_own_ram'] += 1
            c['queen_died_on_loop'] += on_loop
    close()
    flush()
    theirs = 'B' if ours == 'A' else 'A'
    their_queen = next((i for i in (0, 1) if team_of.get(i) == theirs), None)
    queen_len = len(bodies.get(queen) or ()) if alive else 0
    their_len = len(bodies.get(their_queen) or ()) if their_queen is not None else 0
    lead = lead_of()
    full = result.u16(2) == 1
    c['tiles_stood'] = len(stood)
    c['tiles_stood_early'] = len(stood_early)
    c['queen_alive_end'] = int(alive)
    c['queen_final_len'] = queen_len
    c['queen_final_short'] = int(alive and queen_len <= MAX_LEN)
    c['their_queen_alive_end'] = int(their_len > 0)
    c['their_queen_final_len'] = their_len
    c['lead_final_len'] = len(bodies[lead]) if lead is not None else 0
    c['team_final_len'] = sum(len(b) for did, b in bodies.items() if team_of.get(did) == ours)
    c['their_longest_final'] = max((len(b) for did, b in bodies.items() if team_of.get(did) == theirs), default=0)
    c['full_length_games'] = int(full)
    c['ended_by_elimination'] = int(not full)
    c['queen_rule_games'] = int(full and queen_len != their_len)
    c['queen_rule_wins'] = int(full and queen_len > their_len)
    return 'small' if W * H <= 600 else 'big', dict(c), track.hexdigest()


def collect(directory, tag):
    jobs, keys = [], []
    for p in sorted(glob.glob(os.path.join(directory, f'{tag}_*.replay'))):
        stem = os.path.basename(p)[len(tag) + 1:-len('.replay')]
        m, seed, side = stem.rsplit('_', 2)
        jobs.append((p, side))
        keys.append((m, seed, side))
    with cf.ProcessPoolExecutor(int(os.environ.get('CHECK_WORKERS', '4'))) as pool:
        return dict(zip(keys, pool.map(one, jobs)))


def total(rows):
    s = Counter()
    for r in rows:
        s.update(r)
    return s


def share(a, b):
    return a / b if b else 0.0


def pct(a, b):
    return round(100 * share(a, b), 1)


def view(s):
    g = max(1, s['games'])
    left = {k: s['left_' + k] for k in ('tight', 'pearl', 'blocked', 'long', 'foe_seen', 'other') if s['left_' + k]}
    return {'games': s['games'], 'wins': s['win'],
            'queen_decisions': s['decisions'], 'queen_decisions_before_r300': s['decisions_early'],
            'queen_decisions_from_r300': s['decisions_late'],
            'share_2_or_3_long_pct': pct(s['short'], s['decisions']),
            'share_2_or_3_long_before_r300_pct': pct(s['short_early'], s['decisions_early']),
            'share_2_or_3_long_from_r300_pct': pct(s['short_late'], s['decisions_late']),
            'quiet_decisions': s['quiet'], 'quiet_decisions_before_r300': s['quiet_early'],
            'quiet_decisions_from_r300': s['quiet_late'], 'quiet_share_pct': pct(s['quiet'], s['decisions']),
            'decisions_with_an_enemy_head_seen': s['foe_seen'],
            'decisions_with_a_pearl_within_4_steps': s['pearl_near'],
            'lap_steps': s['lap_steps'], 'lap_steps_before_r300': s['lap_steps_early'],
            'lap_steps_from_r300': s['lap_steps_late'],
            'loop_share_pct': pct(s['lap_steps'], s['decisions']),
            'loop_share_before_r300_pct': pct(s['lap_steps_early'], s['decisions_early']),
            'loop_share_from_r300_pct': pct(s['lap_steps_late'], s['decisions_late']),
            'loops': s['loops'], 'lap_steps_per_loop': round(share(s['lap_steps'], s['loops']), 1),
            'loop_share_with_lead_in_pct': pct(s['lap_steps'] + s['lead_in_steps'], s['decisions']),
            'lap_steps_on_quiet_decisions': s['lap_quiet'], 'loop_share_of_quiet_pct': pct(s['lap_quiet'], s['quiet']),
            'lap_steps_on_quiet_decisions_from_r300': s['lap_quiet_late'],
            'loop_share_of_quiet_from_r300_pct': pct(s['lap_quiet_late'], s['quiet_late']),
            'tiles_stood_on': s['tiles_stood'], 'tiles_stood_on_before_r300': s['tiles_stood_early'],
            'tiles_per_100_decisions': round(100 * share(s['tiles_stood'], s['decisions']), 1),
            'steady_loops': s['steady_loops'], 'lap_steps_in_steady_loops': s['steady_n'],
            'steady_lap_steps_within_4_of_spawn': s['steady_home'],
            'steady_lap_steps_with_a_portal_on_or_beside': s['steady_portal'],
            'steady_lap_steps_4_or_longer': s['steady_long'],
            'decisions_after_a_lap_step_where_the_rule_cannot_apply': s['other_lap_decisions'],
            'on_the_loop_decisions': s['on_loop'], 'of_those_going_on': s['on_loop_went_on'],
            'on_the_loop_tight': s['on_loop_tight'], 'tight_and_went_on': s['on_loop_tight_went_on'],
            'on_the_loop_true_tight': s['on_loop_true_tight'], 'true_tight_and_went_on': s['on_loop_true_tight_went_on'],
            'true_tight_she_could_not_tell': s['on_loop_true_tight_unseen'],
            'left_the_loop_because': left, 'died_on_the_action_that_left_the_loop': s['left_died'],
            'push_offs': s['push_offs'], 'push_offs_followed_by_a_lap_step_near_the_pusher': s['push_then_near'],
            'lap_steps_within_4_of_spawn': s['lap_home'], 'lap_steps_with_a_portal_on_or_beside': s['lap_portal'],
            'lap_steps_with_a_pearl_on_or_beside': s['lap_pearl'], 'lap_steps_4_or_longer': s['lap_long'],
            'feed_deaths': s['feed_deaths'], 'feed_deaths_before_r300': s['feed_deaths_early'],
            'feed_deaths_from_r300': s['feed_deaths_late'], 'feed_deaths_while_queen_alive': s['feed_deaths_alive'],
            'of_those_by_the_queen': s['feed_deaths_by_queen'], 'of_those_by_the_lead': s['feed_deaths_by_lead'],
            'of_those_elsewhere': s['feed_deaths_elsewhere'],
            'feed_pearls': s['feed_pearls'],
            'feed_pearls_eaten_by': {k: s['feed_eaten_by_' + k] for k in ('queen', 'lead', 'others', 'enemy')},
            'feed_pearls_eaten_by_our_team_while_queen_alive': s['feed_eaten_alive'],
            'of_those_by_the_queen_pct': pct(s['feed_eaten_alive_by_queen'], s['feed_eaten_alive']),
            'feed_pearls_eaten_while_queen_alive_by': {k: s['feed_eaten_alive_by_' + k] for k in ('queen', 'lead', 'others')},
            'queen_died_to_feed': s['queen_feed_deaths'],
            'queen_pearls_eaten': s['queen_eats'], 'queen_pearls_eaten_before_r300': s['queen_eats_early'],
            'queen_pearls_eaten_from_r300': s['queen_eats_late'], 'queen_splits': s['queen_splits'],
            'queen_deaths': s['queen_deaths'], 'queen_deaths_before_r300': s['queen_deaths_early'],
            'queen_alive_at_end': s['queen_alive_end'], 'queen_alive_at_end_2_or_3_long': s['queen_final_short'],
            'queen_deaths_by_cause': {k: s[f'queen_deaths_{k}'] for k in CAUSE + ['other'] if s[f'queen_deaths_{k}']},
            'queen_rammed_by_an_enemy_head': s['queen_rammed'], 'of_those_right_after_a_lap_step': s['queen_rammed_on_loop'],
            'queen_died_right_after_a_lap_step': s['queen_died_on_loop'], 'queen_rammed_a_head_herself': s['queen_own_ram'],
            'queen_death_round_mean': round(share(s['queen_death_round_sum'], s['queen_deaths']), 1),
            'queen_alive_and_mean_length_at': {f'r{m}': [s[f'alive_r{m}'], round(share(s[f'len_sum_r{m}'], s[f'alive_r{m}']), 2)]
                                               for m in MARKS},
            'lead_mean_length_at': {f'r{m}': [s[f'games_r{m}'], round(share(s[f'lead_len_sum_r{m}'], s[f'games_r{m}']), 1)]
                                    for m in MARKS},
            'queen_final_length_per_game': round(s['queen_final_len'] / g, 2),
            'their_queen_alive_at_end': s['their_queen_alive_end'],
            'their_queen_final_length_per_game': round(s['their_queen_final_len'] / g, 2),
            'lead_final_length_per_game': round(s['lead_final_len'] / g, 1),
            'their_longest_final_length_per_game': round(s['their_longest_final'] / g, 1),
            'team_final_length_per_game': round(s['team_final_len'] / g, 1),
            'games_that_went_500_rounds': s['full_length_games'], 'games_ended_by_elimination': s['ended_by_elimination'],
            'games_decided_on_the_queen_rule': s['queen_rule_games'], 'of_those_won': s['queen_rule_wins'],
            'team_pearls_eaten_by_r50_per_game': round(s['team_eats_r50'] / g, 1),
            'team_pearls_eaten_by_r100_per_game': round(s['team_eats_r100'] / g, 1)}


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
    groups = ('small', 'big')
    b = {g: total(base[k][1] for k in keys if base[k][0] == g) for g in groups}
    c = {g: total(cand[k][1] for k in keys if cand[k][0] == g) for g in groups}
    ball, call = total(b.values()), total(c.values())
    same_track = sum(base[k][2] == cand[k][2] for k in keys)
    moves = ball['moves'] + call['moves']
    hops = ball['hops'] + call['hops']
    if moves and ball['path_mismatch'] + call['path_mismatch'] > 0.02 * moves:
        sys.exit('replay moves do not line up with head updates; the measurement is not valid')
    if hops and ball['hop_mismatch'] + call['hop_mismatch'] > 0.005 * hops:
        sys.exit('head moves do not follow the rebuilt walls and portals; the measurement is not valid')
    bv, cv = view(ball), view(call)

    def loop_share(s):
        return share(s['lap_steps'], s['decisions'])

    def tiles(s):
        return share(s['tiles_stood'], s['decisions'])

    quiet_seen = ball['quiet'] >= QUIET_MIN
    late_seen = ball['alive_r300'] >= LATE_ALIVE_MIN
    fed_seen = ball['feed_eaten_by_queen'] >= BASE_FEED_MIN
    target_seen = quiet_seen and late_seen and fed_seen
    loops_ok = loop_share(call) >= LOOP_SHARE_MIN and loop_share(call) - loop_share(ball) >= LOOP_SHARE_GAIN
    roam_ok = tiles(call) < tiles(ball)
    late_loop_seen = call['quiet_late'] >= LATE_N
    late_loop_ok = late_loop_seen and share(call['lap_quiet_late'], call['quiet_late']) >= LATE_QUIET_LAPS
    unfed_seen = call['feed_eaten_alive'] >= FEED_N
    unfed_ok = unfed_seen and share(call['feed_eaten_alive_by_queen'], call['feed_eaten_alive']) <= QUEEN_FEED_MAX
    tight_seen = call['on_loop_tight'] >= TIGHT_N
    tight_ok = bool(share(call['on_loop_tight_went_on'], call['on_loop_tight']) <= TIGHT_STAY) if tight_seen else None
    push_seen = call['push_offs'] >= PUSH_N
    push_ok = bool(share(call['push_then_near'], call['push_offs']) <= NEAR_MAX) if push_seen else None
    place_seen = call['steady_n'] >= PLACE_N
    place_keys = ('steady_home', 'steady_portal', 'steady_long')
    place_ok = bool(all(call[k] - ball[k] <= PLACE_BAD * call['steady_n'] for k in place_keys)) if place_seen else None
    passed = bool(target_seen and loops_ok and roam_ok and late_loop_ok and unfed_ok and tight_ok is not False
                  and push_ok is not False and place_ok is not False)
    why = []
    if not quiet_seen:
        why.append(f"target not seen: switch-off shows {ball['quiet']} quiet decisions, needs {QUIET_MIN}")
    if not late_seen:
        why.append(f"target not seen: the switch-off queen is alive at r{LATE} in {ball['alive_r300']} games, needs {LATE_ALIVE_MIN}")
    if not fed_seen:
        why.append(f"target not seen: the switch-off queen ate {ball['feed_eaten_by_queen']} feed pearls, needs {BASE_FEED_MIN}")
    if not loops_ok:
        why.append(f"loop share {cv['loop_share_pct']}% with the switch on (switch off {bv['loop_share_pct']}%), needs "
                   f"{round(100 * LOOP_SHARE_MIN)}% and {round(100 * LOOP_SHARE_GAIN)} points above switch-off")
    if not roam_ok:
        why.append(f"tiles per 100 decisions did not go down ({bv['tiles_per_100_decisions']} -> {cv['tiles_per_100_decisions']})")
    if not late_loop_seen:
        why.append(f"the late loop did not come up: {call['quiet_late']} switch-on quiet decisions from r{LATE}, needs {LATE_N}")
    elif not late_loop_ok:
        why.append(f"from r{LATE} only {call['lap_quiet_late']} of {call['quiet_late']} switch-on quiet decisions were lap steps, "
                   f"needs {round(100 * LATE_QUIET_LAPS)}%")
    if not unfed_seen:
        why.append(f"feeding with our queen alive did not come up: our team ate {call['feed_eaten_alive']} feed pearls with the "
                   f"switch on, needs {FEED_N}")
    elif not unfed_ok:
        why.append(f"she ate {call['feed_eaten_alive_by_queen']} of the {call['feed_eaten_alive']} feed pearls our team ate while "
                   f"she was alive, at most {round(100 * QUEEN_FEED_MAX)}% allowed")
    if tight_ok is False:
        why.append(f"she went on in {call['on_loop_tight_went_on']} of {call['on_loop_tight']} tight decisions on the loop")
    if push_ok is False:
        why.append(f"{call['push_then_near']} of {call['push_offs']} push-offs were followed by a lap step near the pusher")
    if place_ok is False:
        why.append(f"square placement in steady loops: near spawn {ball['steady_home']} -> {call['steady_home']}, by a portal "
                   f"{ball['steady_portal']} -> {call['steady_portal']}, taken 4+ long {ball['steady_long']} -> "
                   f"{call['steady_long']}, of {call['steady_n']} switch-on steady lap steps")

    def seen_text(seen, need):
        return '' if seen else f' (not seen: fewer than {need}, not judged)'

    note = (f"QUEEN_LOOP {'shown' if passed else 'NOT shown'} on {len(keys)} paired games. "
            f"Loop share (lap steps per queen decision, whole game): switch off {bv['loop_share_pct']}% "
            f"({ball['lap_steps']} of {ball['decisions']}) -> switch on {cv['loop_share_pct']}% "
            f"({call['lap_steps']} of {call['decisions']}); before r{LATE} {bv['loop_share_before_r300_pct']}% -> "
            f"{cv['loop_share_before_r300_pct']}%, from r{LATE} {bv['loop_share_from_r300_pct']}% "
            f"({ball['lap_steps_late']} of {ball['decisions_late']}) -> {cv['loop_share_from_r300_pct']}% "
            f"({call['lap_steps_late']} of {call['decisions_late']}); loops {ball['loops']} -> {call['loops']}, "
            f"lap steps per loop {bv['lap_steps_per_loop']} -> {cv['lap_steps_per_loop']}. "
            f"Quiet decisions (2-3 long, away from spawn, no enemy head seen, no pearl within {PEARL_STEPS} steps): "
            f"{ball['quiet']} -> {call['quiet']}, of those lap steps {ball['lap_quiet']} -> {call['lap_quiet']}; from r{LATE} "
            f"{ball['quiet_late']} -> {call['quiet_late']}, of those lap steps {ball['lap_quiet_late']} -> {call['lap_quiet_late']}. "
            f"Share of her decisions at length 2-3: before r{LATE} {bv['share_2_or_3_long_before_r300_pct']}% -> "
            f"{cv['share_2_or_3_long_before_r300_pct']}%, from r{LATE} {bv['share_2_or_3_long_from_r300_pct']}% -> "
            f"{cv['share_2_or_3_long_from_r300_pct']}%. Tiles her head stood on per 100 decisions: "
            f"{bv['tiles_per_100_decisions']} -> {cv['tiles_per_100_decisions']}. "
            f"Feeding: feed deaths (our dragons dying on purpose) {ball['feed_deaths']} -> {call['feed_deaths']}; while our queen "
            f"was alive {ball['feed_deaths_alive']} -> {call['feed_deaths_alive']}, of those by the queen "
            f"{ball['feed_deaths_by_queen']} -> {call['feed_deaths_by_queen']}, by our longest other dragon "
            f"{ball['feed_deaths_by_lead']} -> {call['feed_deaths_by_lead']}, elsewhere {ball['feed_deaths_elsewhere']} -> "
            f"{call['feed_deaths_elsewhere']}. Feed pearls our team ate while she was alive {ball['feed_eaten_alive']} -> "
            f"{call['feed_eaten_alive']}: by the queen {ball['feed_eaten_alive_by_queen']} -> {call['feed_eaten_alive_by_queen']}, "
            f"by our longest other dragon {ball['feed_eaten_alive_by_lead']} -> {call['feed_eaten_alive_by_lead']}, by the rest "
            f"{ball['feed_eaten_alive_by_others']} -> {call['feed_eaten_alive_by_others']}. Queen pearls eaten from r{LATE} "
            f"{ball['queen_eats_late']} -> {call['queen_eats_late']}; queen died to feed {ball['queen_feed_deaths']} -> "
            f"{call['queen_feed_deaths']}. "
            f"Stepping off: on the loop with a seen head inside reach + {MARGIN - 1} of the square, "
            f"switch off {ball['on_loop_tight']} decisions, went on in {ball['on_loop_tight_went_on']} -> "
            f"switch on {call['on_loop_tight']} decisions, went on in {call['on_loop_tight_went_on']}"
            + seen_text(tight_seen, TIGHT_N)
            + f"; by the enemy's real length {call['on_loop_true_tight']} decisions, went on in "
            f"{call['on_loop_true_tight_went_on']} (she could not tell in {call['on_loop_true_tight_unseen']}). Why she left the loop, "
            f"switch on: {cv['left_the_loop_because']}. Push-offs {ball['push_offs']} -> {call['push_offs']}, followed by a lap "
            f"step near the pusher {ball['push_then_near']} -> {call['push_then_near']}" + seen_text(push_seen, PUSH_N)
            + f". Square placement, lap steps in steady loops ({STEADY}+ lap steps in a row) {ball['steady_n']} -> "
            f"{call['steady_n']}: within {HOME_CLEAR} of spawn {ball['steady_home']} -> {call['steady_home']}, portal on or beside "
            f"{ball['steady_portal']} -> {call['steady_portal']}, taken 4+ long {ball['steady_long']} -> {call['steady_long']}"
            + seen_text(place_seen, PLACE_N)
            + f"; all lap steps {ball['lap_steps']} -> {call['lap_steps']}: within {HOME_CLEAR} of spawn {ball['lap_home']} -> "
            f"{call['lap_home']}, pearl on or beside {ball['lap_pearl']} -> {call['lap_pearl']} (not gated)"
            + f". Not gated, {len(keys)} games each: queen deaths {bv['queen_deaths']} -> {cv['queen_deaths']}, rammed by an enemy head "
            f"{bv['queen_rammed_by_an_enemy_head']} -> {cv['queen_rammed_by_an_enemy_head']} (right after a lap step "
            f"{bv['of_those_right_after_a_lap_step']} -> {cv['of_those_right_after_a_lap_step']}), alive at the end "
            f"{bv['queen_alive_at_end']} -> {cv['queen_alive_at_end']} (2-3 long {bv['queen_alive_at_end_2_or_3_long']} -> "
            f"{cv['queen_alive_at_end_2_or_3_long']}), their queen alive at the end {bv['their_queen_alive_at_end']} -> "
            f"{cv['their_queen_alive_at_end']}, mean death round {bv['queen_death_round_mean']} -> "
            f"{cv['queen_death_round_mean']}, games decided on the queen rule {bv['games_decided_on_the_queen_rule']} (won "
            f"{bv['of_those_won']}) -> {cv['games_decided_on_the_queen_rule']} (won {cv['of_those_won']}), our longest other dragon "
            f"at the end {bv['lead_final_length_per_game']} -> {cv['lead_final_length_per_game']} per game (their longest "
            f"{bv['their_longest_final_length_per_game']} -> {cv['their_longest_final_length_per_game']}), team pearls by r100 per "
            f"game {bv['team_pearls_eaten_by_r100_per_game']} -> {cv['team_pearls_eaten_by_r100_per_game']}, wins {bv['wins']} -> "
            f"{cv['wins']}, pairs where the queen did exactly the same with the switch on and off {same_track} of {len(keys)}"
            + ('' if passed else '. NOT shown: ' + '; '.join(why)))
    out = {'passed': passed, 'note': note, 'target_seen': bool(target_seen),
           'pairs': len(keys), 'pairs_with_identical_queen_track': same_track, 'maps': sorted({k[0] for k in keys}),
           'pass_rule': {'quiet_min': QUIET_MIN, 'late_alive_min': LATE_ALIVE_MIN, 'base_feed_min': BASE_FEED_MIN,
                         'loop_share_min': LOOP_SHARE_MIN, 'loop_share_gain': LOOP_SHARE_GAIN,
                         'late_n': LATE_N, 'late_quiet_laps': LATE_QUIET_LAPS, 'feed_n': FEED_N, 'queen_feed_max': QUEEN_FEED_MAX,
                         'tight_n': TIGHT_N, 'tight_stay': TIGHT_STAY, 'push_n': PUSH_N, 'near_max': NEAR_MAX,
                         'place_n': PLACE_N, 'place_bad': PLACE_BAD, 'steady': STEADY,
                         'target_quiet_seen': bool(quiet_seen), 'target_late_queen_seen': bool(late_seen),
                         'target_fed_queen_seen': bool(fed_seen), 'loops_ok': bool(loops_ok), 'roams_less_ok': bool(roam_ok),
                         'late_loop_seen': bool(late_loop_seen), 'late_loop_ok': bool(late_loop_ok),
                         'not_fed_seen': bool(unfed_seen), 'not_fed_ok': bool(unfed_ok),
                         'step_off_rule_seen': bool(tight_seen), 'step_off_rule_ok': tight_ok,
                         'stay_away_rule_seen': bool(push_seen), 'stay_away_rule_ok': push_ok,
                         'placement_rule_seen': bool(place_seen), 'placement_rule_ok': place_ok},
           'base': bv, 'candidate': cv,
           'by_map_group': {g: {'base': view(b[g]), 'candidate': view(c[g])} for g in groups},
           'by_map': {m: {'base': view(total(base[k][1] for k in keys if k[0] == m)),
                          'candidate': view(total(cand[k][1] for k in keys if k[0] == m))} for m in sorted({k[0] for k in keys})},
           'model_check': {'queen_moves': moves, 'moves_not_matching_head_updates': ball['path_mismatch'] + call['path_mismatch'],
                           'head_hops': hops, 'hops_not_matching_walls_and_portals': ball['hop_mismatch'] + call['hop_mismatch']},
           'limits': ('measured from replays: the 7x7 view, kelp walls, portals and the remembered enemy size are rebuilt, so a '
                      'few tiles can differ from what the bot marked (it only walks portals it has already seen both ends of); '
                      'a lap step needs a full lap, so the first three steps of every loop are not counted in the loop share '
                      '(the lead-in line adds them back); "tight" is her view of the danger, not the truth: enemies out of '
                      'sight and enemies longer than they look are outside it, and the "real length" counts show how often '
                      'that mattered for heads in view; why she left a loop is a rebuild in a fixed order (tight, pearl, '
                      'length, next tile taken, a head seen, other), not the bot\'s own reason; the square-quality rules '
                      '(open sides, exits, not a pocket) are not rebuilt; a feed death is any of our dragons other than the '
                      'queen dying by its own action, which is how the bot feeds; a feed pearl is a pearl that appears on such '
                      'a body in the round it dies; "by the queen / by the lead" places a feed death by distance, and the lead is our longest '
                      'other dragon, which need not be the dragon the bot calls its leader; a game counts as decided on the '
                      'queen rule when it went 500 rounds and the two queens ended at different lengths (dead = 0); deaths, '
                      'lengths, how games ended and wins are raw counts from a small sample against the release bot, which '
                      'does not hunt queens, so they are not evidence of an outcome')}
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
        sys.exit(f'card 38 check failed: {exc}')
